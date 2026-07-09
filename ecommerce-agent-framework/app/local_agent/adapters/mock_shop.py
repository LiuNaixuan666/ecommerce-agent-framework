"""Mock shop adapter for stable Local Agent demonstrations."""

from __future__ import annotations

from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional

from app.local_agent.adapters.base import PlatformMessage, SendResult


class MockShopAdapter:
    platform = "mock_shop"

    def __init__(
        self,
        agent_id: str = "local-agent-mock",
        shop_id: str = "mock-shop-001",
        product_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.agent_id = agent_id
        self.shop_id = shop_id
        self.product_context = product_context or {
            "platform": self.platform,
            "product_name": "Mock Book Set",
            "sku": "BOOK-001",
            "price": 59.9,
            "currency": "CNY",
            "stock": 28,
            "stock_status": "in_stock",
        }
        self._messages: List[PlatformMessage] = []
        self._events: Deque[PlatformMessage] = deque()
        self._processed_ids: set[str] = set()
        self.sent_messages: List[Dict[str, Any]] = []
        self.handoffs: List[Dict[str, Any]] = []

    def detect_app(self) -> bool:
        return True

    def detect_login_status(self) -> bool:
        return True

    def add_buyer_message(
        self,
        text: str,
        external_conversation_id: str = "mock-conversation-001",
        customer_id: str = "mock-buyer-001",
        customer_name: str = "Mock Buyer",
        observed_at: Optional[datetime] = None,
    ) -> PlatformMessage:
        message_id = f"{external_conversation_id}-{len(self._messages) + 1}"
        message = PlatformMessage(
            platform=self.platform,
            external_conversation_id=external_conversation_id,
            external_message_id=message_id,
            customer_message=text,
            observed_at=observed_at or datetime.now(),
            customer_id=customer_id,
            customer_name=customer_name,
            page_context=dict(self.product_context),
            metadata={
                "agent_type": "self_built_local_agent",
                "adapter": "MockShopAdapter",
                "shop_id": self.shop_id,
            },
        )
        self._messages.append(message)
        self._events.append(message)
        return message

    def read_new_messages(self) -> List[PlatformMessage]:
        new_messages: List[PlatformMessage] = []
        while self._events:
            message = self._events.popleft()
            if message.external_message_id in self._processed_ids:
                continue
            self._processed_ids.add(message.external_message_id)
            new_messages.append(message)
        return new_messages

    def send_text(self, message: PlatformMessage, text: str) -> SendResult:
        self.sent_messages.append(
            {
                "conversation_id": message.external_conversation_id,
                "message_id": message.external_message_id,
                "text": text,
                "sent_at": datetime.now().isoformat(),
            }
        )
        return SendResult(
            request_id="pending",
            merchant_id="default",
            platform=self.platform,
            external_conversation_id=message.external_conversation_id,
            external_message_id=message.external_message_id,
            send_status="success",
            sent_text=text,
            sent_at=datetime.now(),
            agent_id=self.agent_id,
        )

    def mark_handoff(self, message: PlatformMessage, reason: str) -> SendResult:
        self.handoffs.append(
            {
                "conversation_id": message.external_conversation_id,
                "message_id": message.external_message_id,
                "reason": reason,
                "created_at": datetime.now().isoformat(),
            }
        )
        return SendResult(
            request_id="pending",
            merchant_id="default",
            platform=self.platform,
            external_conversation_id=message.external_conversation_id,
            external_message_id=message.external_message_id,
            send_status="handoff",
            agent_id=self.agent_id,
            error_code="HANDOFF_REQUIRED",
            error_message=reason,
        )

    def health_check(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "platform": self.platform,
            "shop_id": self.shop_id,
            "status": "running",
            "watched_window_title": "Mock Shop Workbench",
            "pending_messages": len(self._events),
            "sent_messages": len(self.sent_messages),
            "handoffs": len(self.handoffs),
        }
