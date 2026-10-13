"""In-process publish/subscribe for live run updates (server-sent events)."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class Broker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def subscribe(self, channel: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
        self._subscribers[channel].add(queue)
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers[channel].discard(queue)
        if not self._subscribers[channel]:
            self._subscribers.pop(channel, None)

    def publish(self, channel: str, message: dict[str, Any]) -> None:
        for target in (channel, "*"):
            for queue in list(self._subscribers.get(target, ())):
                if queue.full():
                    # A slow client only needs the latest "changed" notice; drop the oldest message.
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                queue.put_nowait({"channel": channel, **message})
