from __future__ import annotations

import hmac
import logging
import time
from collections.abc import Awaitable, Callable

from aiohttp import web

log = logging.getLogger("grokbot_discord")

# Returns False when the correlation_id is unknown (expired, already answered, or forged).
ReplyHandler = Callable[[str, str], Awaitable[bool]]
MAX_BODY = 256 * 1024


class RateLimit:
    """Fixed-window limiter for the whole callback endpoint."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.per_minute = per_minute
        self._clock = clock
        self._window = 0.0
        self._count = 0

    def allow(self) -> bool:
        now = self._clock()
        if now - self._window >= 60:
            self._window, self._count = now, 0
        self._count += 1
        return self._count <= self.per_minute


def _authorized(header: str, secret: str) -> bool:
    kind, _, token = header.partition(" ")
    return bool(secret) and kind.lower() == "bearer" and hmac.compare_digest(
        token.strip().encode(), secret.encode()
    )


def build_app(secret: str, on_reply: ReplyHandler, limit: RateLimit) -> web.Application:
    app = web.Application(client_max_size=MAX_BODY)

    async def health(_: web.Request) -> web.Response:
        return web.Response(text="ok")

    async def reply(request: web.Request) -> web.Response:
        if not limit.allow():
            return web.Response(status=429, text="rate limited")
        if not _authorized(request.headers.get("Authorization", ""), secret):
            return web.Response(status=401, text="unauthorized")
        try:
            body = await request.json()
        except ValueError:
            return web.Response(status=400, text="invalid json")
        if not isinstance(body, dict) or not body.get("correlation_id"):
            return web.Response(status=400, text="missing correlation_id")
        text = str(body.get("text") or "").strip()
        if not text:
            return web.Response(status=204)
        if not await on_reply(str(body["correlation_id"]), text):
            return web.Response(status=404, text="unknown correlation_id")
        return web.json_response({"ok": True})

    app.router.add_get("/health", health)
    app.router.add_post("/reply", reply)
    return app


async def start_site(app: web.Application, bind: str, port: int) -> web.AppRunner:
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, bind, port).start()
    log.info("callback listening on %s:%s", bind, port)
    return runner
