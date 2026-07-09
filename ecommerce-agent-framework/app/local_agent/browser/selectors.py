"""Selector configuration for browser-backed web chat adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class BrowserChatSelectors:
    root: str
    buyer_messages: str
    reply_input: str
    send_button: str
    sent_messages: str
    message_id_attr: str = "data-message-id"
    conversation_id_attr: str = "data-conversation-id"
    customer_id_attr: str = "data-customer-id"
    customer_name_attr: str = "data-customer-name"
    product_fields: Dict[str, str] = field(default_factory=dict)

