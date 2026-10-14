from grokbot_discord.models import WakePayload
from grokbot_discord.webhook import wake_headers
from tests.conftest import TEST_KEY

PAYLOAD = WakePayload("loops", "ping", "u1", "don", "10", "g1", "1", "http://x/reply", "abc")


def test_bearer_headers():
    assert wake_headers(TEST_KEY) == {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TEST_KEY}",
    }


def test_payload_wire_fields():
    assert list(PAYLOAD.as_dict()) == [
        "bot", "text", "author_id", "author_name", "channel_id",
        "guild_id", "message_id", "reply_url", "correlation_id",
    ]
