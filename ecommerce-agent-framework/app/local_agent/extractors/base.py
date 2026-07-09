"""Extractor contracts for converting page state into agent context."""

from __future__ import annotations

from typing import Any, Dict, Protocol

from app.local_agent.watchers.base import RawMessageEvent


class PageContextExtractor(Protocol):
    def extract_for_message(self, event: RawMessageEvent) -> Dict[str, Any]:
        ...

