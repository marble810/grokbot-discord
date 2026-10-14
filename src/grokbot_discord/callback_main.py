"""Run only the reply callback (no Discord gateway). Used for tunnel smoke tests."""

from __future__ import annotations

import asyncio
import logging
import os
import sys

from grokbot_discord.callback import RateLimit, build_app, start_site
from grokbot_discord.config import ConfigError, load_settings

log = logging.getLogger("grokbot_discord")


async def _run() -> None:
    os.environ["CALLBACK_ONLY"] = "true"
    settings = load_settings()

    async def no_pending(_cid: str, _text: str) -> bool:
        return False

    await start_site(
        build_app(
            settings.callback_secret, no_pending, RateLimit(settings.callback_rate_per_minute)
        ),
        settings.callback_bind,
        settings.callback_port,
    )
    log.info("callback-only; reply_url=%s", settings.reply_url())
    await asyncio.Event().wait()


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )
    try:
        asyncio.run(_run())
    except ConfigError as exc:
        log.error("%s", exc)
        sys.exit(2)


if __name__ == "__main__":
    main()
