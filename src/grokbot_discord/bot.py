from __future__ import annotations

import asyncio
import logging
import sys
import uuid

import aiohttp
import discord

from grokbot_discord.callback import RateLimit, build_app, start_site
from grokbot_discord.config import ConfigError, Settings, load_settings
from grokbot_discord.filters import Dedupe
from grokbot_discord.models import IncomingMessage, WakePayload
from grokbot_discord.pending import Pending, PendingStore
from grokbot_discord.routing import Router
from grokbot_discord.split import split_message
from grokbot_discord.webhook import send_wake

log = logging.getLogger("grokbot_discord")
TIMEOUT_TEXT = "No reply from {bot} in time. Try again."
SWEEP_S = 15.0


def to_incoming(message: discord.Message) -> IncomingMessage:
    return IncomingMessage(
        message_id=str(message.id),
        channel_id=str(message.channel.id),
        guild_id=str(message.guild.id) if message.guild else "",
        author_id=str(message.author.id),
        author_name=str(getattr(message.author, "display_name", message.author.name)),
        author_is_bot=bool(message.author.bot),
        content=message.content or "",
        mention_user_ids=frozenset(str(u.id) for u in message.mentions),
        mention_role_ids=frozenset(str(r.id) for r in message.role_mentions),
    )


class Bridge:
    """Discord-independent orchestration: decide, wake, deliver. Testable without a gateway."""

    def __init__(self, settings: Settings, client: discord.Client) -> None:
        self.settings = settings
        self.client = client
        self.router = Router(settings.bots, settings.default_bot)
        self.dedupe = Dedupe()
        self.pending = PendingStore(settings.in_flight_per_channel, settings.reply_timeout_s)
        self.session: aiohttp.ClientSession | None = None
        self.tasks: set[asyncio.Task[None]] = set()
        self.dry_run_log: list[dict[str, str]] = []

    def spawn(self, coro) -> None:  # type: ignore[no-untyped-def]
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def handle(self, msg: IncomingMessage, self_user_id: str, channel) -> None:  # type: ignore[no-untyped-def]
        hit = self.router.route(msg, self_user_id)
        mentioned = self_user_id in msg.mention_user_ids
        reason = self.settings.policy.drop_reason(
            msg, self_user_id=self_user_id, addressed=hit is not None or mentioned
        )
        if reason or self.dedupe.already_seen(msg.message_id):
            return
        if hit is None:
            await channel.send(f"unknown bot. configured: {', '.join(self.router.names)}")
            return
        correlation_id = uuid.uuid4().hex
        if not self.pending.try_add(correlation_id, msg.channel_id, msg.message_id, hit.bot.name):
            await channel.send("busy: too many requests waiting in this channel.")
            return
        payload = WakePayload(
            bot=hit.bot.name,
            text=hit.text,
            author_id=msg.author_id,
            author_name=msg.author_name,
            channel_id=msg.channel_id,
            guild_id=msg.guild_id,
            message_id=msg.message_id,
            reply_url=self.settings.reply_url(),
            correlation_id=correlation_id,
        )
        self.spawn(self._wake(hit.bot.webhook_url, hit.bot.webhook_key, payload))

    async def _wake(self, url: str, key: str, payload: WakePayload) -> None:
        if self.settings.dry_run:
            self.dry_run_log.append(payload.as_dict())
            log.info("DRY_RUN would POST webhook for bot=%s", payload.bot)
            self.pending.take(payload.correlation_id)
            return
        ok = False
        try:
            assert self.session is not None
            ok = await send_wake(self.session, url, key, payload)
        except (TimeoutError, aiohttp.ClientError):
            log.exception("webhook wake failed for bot=%s", payload.bot)
        if not ok:
            log.warning("webhook wake rejected for bot=%s", payload.bot)
            if self.pending.take(payload.correlation_id) is not None:
                await self._send(payload.channel_id, f"Could not wake {payload.bot}.")

    async def on_reply(self, correlation_id: str, text: str) -> bool:
        entry = self.pending.take(correlation_id)
        if entry is None:
            return False
        await self._send(entry.channel_id, text, entry.message_id)
        return True

    async def expire(self) -> list[Pending]:
        gone = self.pending.take_expired()
        for p in gone:
            await self._send(p.channel_id, TIMEOUT_TEXT.format(bot=p.bot), p.message_id)
        return gone

    async def _send(self, channel_id: str, text: str, reply_to: str = "") -> None:
        try:
            channel = self.client.get_channel(int(channel_id)) or await self.client.fetch_channel(
                int(channel_id)
            )
            for i, chunk in enumerate(split_message(text)):
                ref = None
                if i == 0 and reply_to:
                    ref = discord.MessageReference(
                        message_id=int(reply_to),
                        channel_id=int(channel_id),
                        fail_if_not_exists=False,
                    )
                await channel.send(chunk, reference=ref)
        except Exception:
            log.exception("send failed channel=%s", channel_id)


class BridgeClient(discord.Client):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.settings = settings
        self.bridge = Bridge(settings, self)
        self._runner = None

    async def setup_hook(self) -> None:
        self.bridge.session = aiohttp.ClientSession()
        self._runner = await start_callback(self.settings, self.bridge.on_reply)
        self.bridge.spawn(self._sweep())

    async def _sweep(self) -> None:
        while True:
            await asyncio.sleep(SWEEP_S)
            await self.bridge.expire()

    async def close(self) -> None:
        if self.bridge.session is not None:
            await self.bridge.session.close()
        if self._runner is not None:
            await self._runner.cleanup()
        await super().close()

    async def on_ready(self) -> None:
        log.info("online as %s; reply_url=%s", self.user, self.settings.reply_url())

    async def on_message(self, message: discord.Message) -> None:
        if self.user is not None:
            await self.bridge.handle(to_incoming(message), str(self.user.id), message.channel)


async def start_callback(settings: Settings, on_reply):  # type: ignore[no-untyped-def]
    app = build_app(
        settings.callback_secret, on_reply, RateLimit(settings.callback_rate_per_minute)
    )
    return await start_site(app, settings.callback_bind, settings.callback_port)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    try:
        settings = load_settings()
    except ConfigError as exc:
        log.error("%s", exc)
        sys.exit(2)
    if not settings.discord_token:
        log.error("DISCORD_BOT_TOKEN is empty; use --callback-only to test the callback server")
        sys.exit(2)
    BridgeClient(settings).run(settings.discord_token, log_handler=None)
