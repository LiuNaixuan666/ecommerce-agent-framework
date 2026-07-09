"""Conversation queue helpers for Local Agent processing."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict, List

from app.local_agent.adapters.base import PlatformMessage


class SessionQueue:
    def __init__(self) -> None:
        self._queues: Dict[str, Deque[PlatformMessage]] = defaultdict(deque)

    def push(self, message: PlatformMessage) -> None:
        self._queues[message.external_conversation_id].append(message)

    def drain_conversation_serial(self) -> List[PlatformMessage]:
        drained: List[PlatformMessage] = []
        for conversation_id in list(self._queues.keys()):
            queue = self._queues[conversation_id]
            while queue:
                drained.append(queue.popleft())
            if not queue:
                del self._queues[conversation_id]
        return drained

    def drain_round_robin(self) -> List[PlatformMessage]:
        return self.drain_conversation_serial()

    def size(self) -> int:
        return sum(len(queue) for queue in self._queues.values())
