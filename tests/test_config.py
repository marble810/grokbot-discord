import pytest

from grokbot_discord.config import ConfigError, load_settings


def test_load_ok(example_env):
    s = load_settings(example_env / ".env", example_env / "bots.yaml")
    assert "g1" in s.policy.guilds
    assert s.bots["loops"].webhook_secret.startswith("whsec_")
    assert s.default_bot == "loops"
    assert s.reply_url() == "http://127.0.0.1:8787/reply"


def test_url_file_wins_and_is_reread(example_env, monkeypatch):
    url_file = example_env / "public_url"
    monkeypatch.setenv("CALLBACK_PUBLIC_URL_FILE", str(url_file))
    s = load_settings(example_env / ".env", example_env / "bots.yaml")
    assert s.reply_url() == "http://127.0.0.1:8787/reply"
    url_file.write_text("https://a.trycloudflare.com/\n")
    assert s.reply_url() == "https://a.trycloudflare.com/reply"


@pytest.mark.parametrize(
    "line", ["DISCORD_GUILD_ALLOWLIST=g1", "DISCORD_AUTHOR_ALLOWLIST=u1", "CALLBACK_SECRET="]
)
def test_fail_closed(example_env, line):
    env = example_env / ".env"
    key = line.split("=")[0]
    env.write_text(
        "\n".join(x for x in env.read_text().splitlines() if not x.startswith(key + "=")) + "\n"
    )
    with pytest.raises(ConfigError):
        load_settings(env, example_env / "bots.yaml")


def test_missing_webhook_secret(example_env):
    env = example_env / ".env"
    env.write_text(
        "\n".join(x for x in env.read_text().splitlines() if "WEBHOOK_SECRET" not in x) + "\n"
    )
    with pytest.raises(ConfigError, match="WEBHOOK_SECRET"):
        load_settings(env, example_env / "bots.yaml")
