from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class BotSpec:
    name: str
    aliases: tuple[str, ...]
    role_id: str
    webhook_url: str
    webhook_secret: str


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    channel_id: str
    guild_id: str
    author_id: str
    author_name: str
    author_is_bot: bool
    content: str
    mention_user_ids: frozenset[str]
    mention_role_ids: frozenset[str]


@dataclass(frozen=True)
class Route:
    bot: BotSpec
    text: str


@dataclass(frozen=True)
class WakePayload:
    """The JSON body sent to a Grok Bot routine. Field order is the wire order."""

    bot: str
    text: str
    author_id: str
    author_name: str
    channel_id: str
    guild_id: str
    message_id: str
    reply_url: str
    correlation_id: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)
