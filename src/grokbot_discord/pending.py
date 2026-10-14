"""Wakes waiting for a callback: per-channel slots plus a TTL so slots cannot leak."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Pending:
    channel_id: str
    message_id: str
    bot: str
    deadline: float


@dataclass
class PendingStore:
    max_per_channel: int
    ttl_s: float
    clock: Callable[[], float] = time.monotonic
    _items: dict[str, Pending] = field(default_factory=dict)

    def in_channel(self, channel_id: str) -> int:
        return sum(1 for p in self._items.values() if p.channel_id == channel_id)

    def try_add(self, correlation_id: str, channel_id: str, message_id: str, bot: str) -> bool:
        if self.in_channel(channel_id) >= self.max_per_channel:
            return False
        self._items[correlation_id] = Pending(
            channel_id, message_id, bot, self.clock() + self.ttl_s
        )
        return True

    def take(self, correlation_id: str) -> Pending | None:
        return self._items.pop(correlation_id, None)

    def take_expired(self) -> list[Pending]:
        now = self.clock()
        gone = [cid for cid, p in self._items.items() if p.deadline <= now]
        return [self._items.pop(cid) for cid in gone]
