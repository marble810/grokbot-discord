"""Wake a Grok Bot routine: POST JSON with `Authorization: Bearer <crsr_… key>`."""

from __future__ import annotations

import aiohttp

from grokbot_discord.models import WakePayload

WEBHOOK_TIMEOUT_S = 8.0


def wake_headers(key: str) -> dict[str, str]:
    return {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}


async def send_wake(
    session: aiohttp.ClientSession, url: str, key: str, payload: WakePayload
) -> bool:
    """POST the wake. True on any 2xx (routines answer 200)."""
    async with session.post(
        url,
        json=payload.as_dict(),
        headers=wake_headers(key),
        timeout=aiohttp.ClientTimeout(total=WEBHOOK_TIMEOUT_S),
    ) as resp:
        return 200 <= resp.status < 300
