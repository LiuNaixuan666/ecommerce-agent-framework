"""Base adapter contracts for the self-built Local Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class PlatformMessage:
    platform: str
    external_conversation_id: str
    external_message_id: str
    customer_message: str
    observed_at: datetime = field(default_factory=datetime.now)
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    page_context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SendResult:
    request_id: str
    merchant_id: str
    platform: str
    external_conversation_id: str
    external_message_id: Optional[str]
    send_status: str
    sent_text: Optional[str] = None
    sent_at: Optional[datetime] = None
    agent_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BasePlatformAdapter(Protocol):
    platform: str

    def detect_app(self) -> bool:
        ...

    def detect_login_status(self) -> bool:
        ...

    def read_new_messages(self) -> List[PlatformMessage]:
        ...

    def send_text(self, message: PlatformMessage, text: str) -> SendResult:
        ...

    def mark_handoff(self, message: PlatformMessage, reason: str) -> SendResult:
        ...

    def health_check(self) -> Dict[str, Any]:
        ...
