"""Wake a Grok Bot routine with a Standard Webhooks signed POST."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid

import aiohttp

from grokbot_discord.models import WakePayload

WEBHOOK_TIMEOUT_S = 8.0


def decode_secret(secret: str) -> bytes:
    return base64.b64decode(secret.removeprefix("whsec_"))


def sign(secret: str, webhook_id: str, timestamp: str, body: bytes) -> str:
    signed = f"{webhook_id}.{timestamp}.".encode() + body
    digest = hmac.new(decode_secret(secret), signed, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def signed_headers(secret: str, body: bytes, *, now: int | None = None) -> dict[str, str]:
    webhook_id = f"msg_{uuid.uuid4().hex}"
    timestamp = str(int(time.time()) if now is None else now)
    return {
        "content-type": "application/json",
        "webhook-id": webhook_id,
        "webhook-timestamp": timestamp,
        "webhook-signature": sign(secret, webhook_id, timestamp, body),
    }


def encode(payload: WakePayload) -> bytes:
    return json.dumps(payload.as_dict(), separators=(",", ":")).encode()


async def send_wake(
    session: aiohttp.ClientSession, url: str, secret: str, payload: WakePayload
) -> bool:
    """POST the signed wake. True on any 2xx (Grok answers 202 Accepted)."""
    body = encode(payload)
    async with session.post(
        url,
        data=body,
        headers=signed_headers(secret, body),
        timeout=aiohttp.ClientTimeout(total=WEBHOOK_TIMEOUT_S),
    ) as resp:
        return 200 <= resp.status < 300
