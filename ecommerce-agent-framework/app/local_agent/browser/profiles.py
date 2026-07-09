"""Browser selector profiles for web customer service pages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.local_agent.browser.selectors import BrowserChatSelectors


@dataclass
class BrowserChatProfile:
    name: str
    platform: str
    selectors: BrowserChatSelectors
    default_url: Optional[str] = None
    default_conversation_id: str = "browser-conversation"


def browser_mock_profile() -> BrowserChatProfile:
    page_path = Path(__file__).resolve().parents[1] / "mock_pages" / "browser_chat.html"
    return BrowserChatProfile(
        name="browser_mock",
        platform="browser_mock",
        default_url=page_path.as_uri(),
        default_conversation_id="browser-conv-001",
        selectors=BrowserChatSelectors(
            root="[data-testid='chat-root']",
            buyer_messages="[data-testid='buyer-message']",
            reply_input="[data-testid='reply-input']",
            send_button="[data-testid='send-button']",
            sent_messages="[data-testid='sent-message']",
            product_fields={
                "product_name": "[data-testid='product-name']",
                "sku": "[data-testid='sku']",
                "stock": "[data-testid='stock']",
            },
        ),
    )


def pinduoduo_web_profile() -> BrowserChatProfile:
    return BrowserChatProfile(
        name="pinduoduo_web",
        platform="pinduoduo",
        default_url="https://mms.pinduoduo.com/chat-merchant/index.html",
        default_conversation_id="pdd-browser-conversation",
        selectors=BrowserChatSelectors(
            root="body",
            buyer_messages="__pdd_auto_buyer_messages__",
            reply_input="__pdd_auto_reply_input__",
            send_button="__pdd_auto_send_button__",
            sent_messages="__pdd_auto_sent_messages__",
        ),
    )


def get_builtin_profile(name: str) -> BrowserChatProfile:
    if name == "browser_mock":
        return browser_mock_profile()
    if name == "pinduoduo_web":
        return pinduoduo_web_profile()
    raise ValueError(f"Unknown built-in browser chat profile: {name}")


def load_profile_from_json(path: str | Path) -> BrowserChatProfile:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    selectors = raw.get("selectors") or {}
    required = ["root", "buyer_messages", "reply_input", "send_button", "sent_messages"]
    missing = [key for key in required if not selectors.get(key)]
    if missing:
        raise ValueError(f"Selector profile missing required selectors: {', '.join(missing)}")

    return BrowserChatProfile(
        name=raw.get("name") or Path(path).stem,
        platform=raw.get("platform") or raw.get("name") or Path(path).stem,
        default_url=raw.get("default_url"),
        default_conversation_id=raw.get("default_conversation_id", "browser-conversation"),
        selectors=BrowserChatSelectors(
            root=selectors["root"],
            buyer_messages=selectors["buyer_messages"],
            reply_input=selectors["reply_input"],
            send_button=selectors["send_button"],
            sent_messages=selectors["sent_messages"],
            message_id_attr=selectors.get("message_id_attr", "data-message-id"),
            conversation_id_attr=selectors.get("conversation_id_attr", "data-conversation-id"),
            customer_id_attr=selectors.get("customer_id_attr", "data-customer-id"),
            customer_name_attr=selectors.get("customer_name_attr", "data-customer-name"),
            product_fields=_string_dict(selectors.get("product_fields") or {}),
        ),
    )


def _string_dict(value: Dict[str, Any]) -> Dict[str, str]:
    return {str(key): str(item) for key, item in value.items()}
