"""Watcher contracts for reading raw page events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class RawMessageEvent:
    platform: str
    external_conversation_id: str
    external_message_id: str
    text: str
    observed_at: datetime = field(default_factory=datetime.now)
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class MessageWatcher(Protocol):
    def detect_app(self) -> bool:
        ...

    def detect_login_status(self) -> bool:
        ...

    def read_events(self) -> List[RawMessageEvent]:
        ...

    def health_check(self) -> Dict[str, Any]:
        ...
