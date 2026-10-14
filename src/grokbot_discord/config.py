from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

from grokbot_discord.filters import Policy
from grokbot_discord.models import BotSpec


class ConfigError(ValueError):
    pass


def parse_id_list(raw: str) -> frozenset[str]:
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def _truthy(raw: str | None, default: bool) -> bool:
    if not raw:
        return default
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    discord_token: str
    policy: Policy
    default_bot: str
    bots: dict[str, BotSpec]
    callback_secret: str
    callback_bind: str
    callback_port: int
    callback_public_url: str
    callback_public_url_file: Path | None
    callback_rate_per_minute: int
    dry_run: bool
    in_flight_per_channel: int
    reply_timeout_s: float

    def public_base_url(self) -> str:
        """Public callback base. A URL file (written by the tunnel script) wins over env,
        and is re-read on every wake so a restarted quick tunnel needs no bridge restart."""
        if self.callback_public_url_file and self.callback_public_url_file.is_file():
            url = self.callback_public_url_file.read_text(encoding="utf-8").strip()
            if url:
                return url.rstrip("/")
        return self.callback_public_url

    def reply_url(self) -> str:
        return f"{self.public_base_url()}/reply"


def _env_name(bot: str, suffix: str) -> str:
    return f"GROK_BOT_{bot.upper().replace('-', '_')}_{suffix}"


def load_bots(path: Path, *, dry_run: bool) -> tuple[str, dict[str, BotSpec]]:
    if not path.is_file():
        raise ConfigError(f"bots file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    default = str(data.get("default") or "")
    raw_bots = data.get("bots") or {}
    if not raw_bots:
        raise ConfigError("bots list is empty")
    bots: dict[str, BotSpec] = {}
    for name, spec in raw_bots.items():
        spec = spec or {}
        url_env = str(spec.get("webhook_url_env") or _env_name(name, "WEBHOOK_URL"))
        key_env = str(spec.get("webhook_key_env") or _env_name(name, "WEBHOOK_KEY"))
        url = os.environ.get(url_env, "")
        # Fallback: older configs named the key _WEBHOOK_SECRET.
        key = os.environ.get(key_env, "") or os.environ.get(_env_name(name, "WEBHOOK_SECRET"), "")
        # Callback-only / dry-run skips live webhook credentials.
        need_hooks = not dry_run and not _truthy(os.environ.get("CALLBACK_ONLY"), False)
        if need_hooks:
            if not url:
                raise ConfigError(f"{name}: missing webhook URL ({url_env})")
            if not key:
                raise ConfigError(f"{name}: missing webhook key ({key_env})")
        bots[name] = BotSpec(
            name=name,
            aliases=tuple(str(a) for a in (spec.get("aliases") or [name])),
            role_id=str(spec.get("role_id") or ""),
            webhook_url=url,
            webhook_key=key,
        )
    if default and default not in bots:
        raise ConfigError(f"default bot {default!r} is not in bots")
    return default, bots


def _required_ids(name: str) -> frozenset[str]:
    ids = parse_id_list(os.environ.get(name, ""))
    if not ids:
        raise ConfigError(f"{name} is empty")
    return ids


def load_settings(env_file: Path | None = None, bots_file: Path | None = None) -> Settings:
    load_dotenv(env_file or Path(".env"))
    env = os.environ.get
    dry_run = _truthy(env("DRY_RUN"), False)
    callback_only = _truthy(env("CALLBACK_ONLY"), False)
    token = env("DISCORD_BOT_TOKEN", "")
    if not token and not dry_run and not callback_only:
        raise ConfigError("DISCORD_BOT_TOKEN is empty")
    policy = Policy(
        guilds=_required_ids("DISCORD_GUILD_ALLOWLIST"),
        channels=_required_ids("DISCORD_CHANNEL_ALLOWLIST"),
        authors=_required_ids("DISCORD_AUTHOR_ALLOWLIST"),
        require_mention=_truthy(env("REQUIRE_MENTION"), True),
    )
    default_from_file, bots = load_bots(
        bots_file or Path(env("BOTS_FILE", "bots.yaml")), dry_run=dry_run
    )
    default_bot = env("DEFAULT_BOT", "") or default_from_file
    if default_bot and default_bot not in bots:
        raise ConfigError(f"DEFAULT_BOT {default_bot!r} is not in bots")
    secret = env("CALLBACK_SECRET", "")
    if len(secret) < 24:
        raise ConfigError("CALLBACK_SECRET must be at least 24 characters")
    port = int(env("CALLBACK_PORT", "8787"))
    url_file = env("CALLBACK_PUBLIC_URL_FILE", "")
    return Settings(
        discord_token=token,
        policy=policy,
        default_bot=default_bot,
        bots=bots,
        callback_secret=secret,
        callback_bind=env("CALLBACK_BIND", "127.0.0.1"),
        callback_port=port,
        callback_public_url=env("CALLBACK_PUBLIC_URL", f"http://127.0.0.1:{port}").rstrip("/"),
        callback_public_url_file=Path(url_file) if url_file else None,
        callback_rate_per_minute=int(env("CALLBACK_RATE_PER_MINUTE", "30")),
        dry_run=dry_run,
        in_flight_per_channel=int(env("IN_FLIGHT_PER_CHANNEL", "2")),
        reply_timeout_s=float(env("REPLY_TIMEOUT_S", "900")),
    )
