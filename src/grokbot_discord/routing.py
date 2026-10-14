from __future__ import annotations

import re
from dataclasses import dataclass, field

from grokbot_discord.models import BotSpec, IncomingMessage, Route


def strip_user_mention(content: str, user_id: str) -> str:
    return re.sub(rf"<@!?{re.escape(user_id)}>", "", content)


@dataclass
class Router:
    """Resolves which Grok Bot a message addresses. None means not addressed to any bot."""

    bots: dict[str, BotSpec]
    default_bot: str = ""
    _aliases: dict[str, BotSpec] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        aliases: dict[str, BotSpec] = {}
        for bot in self.bots.values():
            for alias in (bot.name, *bot.aliases):
                aliases[alias.casefold()] = bot
        self._aliases = aliases

    @property
    def names(self) -> list[str]:
        return sorted(self.bots)

    def route(self, msg: IncomingMessage, self_user_id: str) -> Route | None:
        text = strip_user_mention(msg.content, self_user_id).strip()

        roles = [b for b in self.bots.values() if b.role_id and b.role_id in msg.mention_role_ids]
        if len(roles) == 1:
            bot = roles[0]
            return Route(bot=bot, text=text.replace(f"<@&{bot.role_id}>", "").strip())
        if len(roles) > 1:
            return None

        first, _, rest = text.partition(" ")
        hit = self._aliases.get(first.lstrip("@").casefold())
        if hit is not None:
            return Route(bot=hit, text=rest.strip())

        if self.default_bot and self_user_id in msg.mention_user_ids:
            return Route(bot=self.bots[self.default_bot], text=text)
        return None
