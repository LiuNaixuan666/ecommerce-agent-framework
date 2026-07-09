"""Browser page context extractor."""

from __future__ import annotations

from typing import Any, Dict

from app.local_agent.browser.selectors import BrowserChatSelectors
from app.local_agent.watchers.base import RawMessageEvent


class BrowserPageContextExtractor:
    def __init__(self, page: Any, selectors: BrowserChatSelectors) -> None:
        self.page = page
        self.selectors = selectors

    def extract_for_message(self, event: RawMessageEvent) -> Dict[str, Any]:
        context: Dict[str, Any] = {"platform": event.platform}
        for key, selector in self.selectors.product_fields.items():
            value = self._read_text(selector)
            if value is not None:
                context[key] = value
        return context

    def _read_text(self, selector: str) -> str | None:
        try:
            locator = self.page.locator(selector)
            if locator.count() <= 0:
                return None
            return locator.first.inner_text().strip()
        except Exception:
            return None

