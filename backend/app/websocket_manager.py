"""WebSocket helpers: single-active-client slot and a bounded outbound buffer."""

from __future__ import annotations

import asyncio
from collections import deque
from typing import Any


class ClientSlot:
    """Allows exactly one active gesture client (the camera is a shared hardware resource)."""

    def __init__(self) -> None:
        self._owner: object | None = None

    def try_acquire(self, owner: object) -> bool:
        if self._owner is not None:
            return False
        self._owner = owner
        return True

    def release(self, owner: object) -> None:
        if self._owner is owner:
            self._owner = None

    @property
    def occupied(self) -> bool:
        return self._owner is not None


class OutboundBuffer:
    """Bounded latest-state buffer. Stale gesture ``update`` events are dropped first when full;
    required start/end transitions and status/error messages are never dropped.
    Must be used from the event loop thread only."""

    def __init__(self, max_pending: int = 64) -> None:
        self._max = max_pending
        self._items: deque[dict[str, Any]] = deque()
        self._event = asyncio.Event()

    def push(self, msg: dict[str, Any]) -> None:
        if len(self._items) >= self._max:
            self._drop_oldest_update()
        self._items.append(msg)
        self._event.set()

    def _drop_oldest_update(self) -> None:
        for i, m in enumerate(self._items):
            if m.get("type") == "gesture" and m.get("phase") == "update":
                del self._items[i]
                return

    async def get_batch(self) -> list[dict[str, Any]]:
        await self._event.wait()
        self._event.clear()
        batch = list(self._items)
        self._items.clear()
        return batch

    def __len__(self) -> int:
        return len(self._items)
