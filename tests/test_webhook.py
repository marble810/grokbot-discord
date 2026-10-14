import base64
import hashlib
import hmac
import json

from grokbot_discord.models import WakePayload
from grokbot_discord.webhook import encode, signed_headers
from tests.conftest import TEST_SECRET

PAYLOAD = WakePayload("loops", "ping", "u1", "don", "10", "g1", "1", "https://x/reply", "abc")


def test_signature_matches_standard_webhooks():
    body = encode(PAYLOAD)
    h = signed_headers(TEST_SECRET, body, now=1700000000)
    key = base64.b64decode(TEST_SECRET.removeprefix("whsec_"))
    signed = f"{h['webhook-id']}.{h['webhook-timestamp']}.".encode() + body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode()
    assert h["webhook-signature"] == f"v1,{expected}"
    assert h["webhook-timestamp"] == "1700000000"
    assert h["webhook-id"].startswith("msg_")
    assert "authorization" not in {k.lower() for k in h}


def test_payload_wire_fields():
    assert list(json.loads(encode(PAYLOAD))) == [
        "bot", "text", "author_id", "author_name", "channel_id",
        "guild_id", "message_id", "reply_url", "correlation_id",
    ]
