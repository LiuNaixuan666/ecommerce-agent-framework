"""Executor contracts for sending replies back to a platform page."""

from __future__ import annotations

from typing import Protocol

from app.local_agent.adapters.base import PlatformMessage, SendResult


class ReplyExecutor(Protocol):
    def send_text(self, message: PlatformMessage, text: str) -> SendResult:
        ...

    def mark_handoff(self, message: PlatformMessage, reason: str) -> SendResult:
        ...

