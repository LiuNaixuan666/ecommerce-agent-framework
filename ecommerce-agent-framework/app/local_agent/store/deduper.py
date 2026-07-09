"""Simple in-memory event deduper."""

from __future__ import annotations

from collections import deque
from typing import Deque, Set


class EventDeduper:
    def __init__(self, max_size: int = 2000) -> None:
        self.max_size = max_size
        self._seen: Set[str] = set()
        self._order: Deque[str] = deque()

    def is_new(self, event_id: str) -> bool:
        if event_id in self._seen:
            return False
        self._seen.add(event_id)
        self._order.append(event_id)
        self._trim()
        return True

    def _trim(self) -> None:
        while len(self._order) > self.max_size:
            oldest = self._order.popleft()
            self._seen.discard(oldest)

