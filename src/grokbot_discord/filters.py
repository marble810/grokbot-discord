from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from grokbot_discord.models import IncomingMessage


class Dedupe:
    def __init__(self, cap: int = 1024) -> None:
        self._cap = cap
        self._seen: OrderedDict[str, None] = OrderedDict()

    def already_seen(self, message_id: str) -> bool:
        if message_id in self._seen:
            return True
        self._seen[message_id] = None
        if len(self._seen) > self._cap:
            self._seen.popitem(last=False)
        return False


@dataclass(frozen=True)
class Policy:
    """Who may wake a bot, and where. Allowlists are non-empty (enforced by config)."""

    guilds: frozenset[str]
    channels: frozenset[str]
    authors: frozenset[str]
    require_mention: bool = True

    def drop_reason(
        self, msg: IncomingMessage, *, self_user_id: str, addressed: bool
    ) -> str | None:
        if msg.author_is_bot or msg.author_id == self_user_id:
            return "bot"
        if msg.guild_id not in self.guilds:
            return "guild"
        if msg.channel_id not in self.channels:
            return "channel"
        if msg.author_id not in self.authors:
            return "author"
        if self.require_mention and not addressed:
            return "mention"
        return None
