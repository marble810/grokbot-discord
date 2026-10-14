from __future__ import annotations

from pathlib import Path

import pytest

from grokbot_discord.models import BotSpec, IncomingMessage

TEST_SECRET = "whsec_" + "dGVzdC1zaWduaW5nLXNlY3JldC0xMjM0NTY3ODkw"


def make_msg(**overrides) -> IncomingMessage:
    base = dict(
        message_id="1",
        channel_id="10",
        guild_id="g1",
        author_id="u1",
        author_name="don",
        author_is_bot=False,
        content="<@99> loops ping",
        mention_user_ids=frozenset({"99"}),
        mention_role_ids=frozenset(),
    )
    base.update(overrides)
    return IncomingMessage(**base)


@pytest.fixture
def bots() -> dict[str, BotSpec]:
    return {
        "loops": BotSpec("loops", ("loops", "loop"), "role-loops", "https://e.test/l", TEST_SECRET),
        "xo": BotSpec("xo", ("xo",), "role-xo", "https://e.test/x", TEST_SECRET),
    }


@pytest.fixture
def example_env(tmp_path: Path, monkeypatch) -> Path:
    import os

    for key in list(os.environ):
        if key.startswith(("DISCORD_", "GROK_BOT_", "CALLBACK_", "DRY_RUN", "DEFAULT_BOT")):
            monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(
        "DISCORD_BOT_TOKEN=dummy-token\n"
        "DISCORD_GUILD_ALLOWLIST=g1\n"
        "DISCORD_CHANNEL_ALLOWLIST=10\n"
        "DISCORD_AUTHOR_ALLOWLIST=u1\n"
        "CALLBACK_SECRET=callback-secret-callback-secret\n"
        "GROK_BOT_LOOPS_WEBHOOK_URL=https://e.test/hooks/loops\n"
        f"GROK_BOT_LOOPS_WEBHOOK_SECRET={TEST_SECRET}\n",
        encoding="utf-8",
    )
    (tmp_path / "bots.yaml").write_text(
        "default: loops\nbots:\n  loops:\n    aliases: [loops]\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path
