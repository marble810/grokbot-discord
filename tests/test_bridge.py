from types import SimpleNamespace

import pytest

from grokbot_discord.bot import ACK_TEXT, Bridge
from grokbot_discord.config import load_settings
from tests.conftest import make_msg


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, text, reference=None):
        self.sent.append(text)


class FakeClient:
    def __init__(self, channel):
        self.channel = channel

    def get_channel(self, _id):
        return self.channel


@pytest.fixture
def bridge(example_env, monkeypatch):
    monkeypatch.setenv("REPLY_TIMEOUT_S", "0")
    settings = load_settings(example_env / ".env", example_env / "bots.yaml")
    channel = FakeChannel()
    b = Bridge(settings, FakeClient(channel))
    woke = []

    async def fake_wake(url, secret, payload):
        woke.append(payload)

    b._wake = fake_wake
    b.spawn = lambda coro: __import__("asyncio").ensure_future(coro)
    return SimpleNamespace(b=b, channel=channel, woke=woke)


async def _settle():
    import asyncio

    await asyncio.sleep(0)


async def test_wake_then_reply(bridge):
    await bridge.b.handle(make_msg(), "99", bridge.channel)
    await _settle()
    assert bridge.channel.sent == [ACK_TEXT]
    payload = bridge.woke[0]
    assert payload.reply_url.endswith("/reply") and payload.text == "ping"
    assert await bridge.b.on_reply(payload.correlation_id, "pong")
    assert bridge.channel.sent[-1] == "pong"
    assert not await bridge.b.on_reply(payload.correlation_id, "again")


async def test_bot_author_and_duplicates_ignored(bridge):
    await bridge.b.handle(make_msg(author_is_bot=True), "99", bridge.channel)
    await bridge.b.handle(make_msg(message_id="2"), "99", bridge.channel)
    await bridge.b.handle(make_msg(message_id="2"), "99", bridge.channel)
    await _settle()
    assert len(bridge.woke) == 1


async def test_timeout_releases_slot_and_notifies(bridge):
    for i in range(3):
        await bridge.b.handle(make_msg(message_id=str(i + 1)), "99", bridge.channel)
    await _settle()
    assert len(bridge.woke) == 2 and bridge.channel.sent[-1].startswith("busy")
    expired = await bridge.b.expire()
    assert len(expired) == 2
    assert bridge.channel.sent[-1].startswith("No reply from loops")
    await bridge.b.handle(make_msg(message_id="9"), "99", bridge.channel)
    await _settle()
    assert len(bridge.woke) == 3


async def test_unknown_bot(bridge):
    bridge.b.router = type(bridge.b.router)(bridge.b.settings.bots, "")
    await bridge.b.handle(make_msg(content="<@99> nope hi"), "99", bridge.channel)
    await _settle()
    assert bridge.channel.sent[-1].startswith("unknown bot")
