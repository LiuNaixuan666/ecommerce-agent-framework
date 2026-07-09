"""Browser page reply executor."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.local_agent.adapters.base import PlatformMessage, SendResult
from app.local_agent.browser.selectors import BrowserChatSelectors


class BrowserPageReplyExecutor:
    def __init__(
        self,
        page: Any,
        selectors: BrowserChatSelectors,
        agent_id: str = "local-agent-browser",
        verify_timeout_ms: int = 3000,
        dry_run: bool = False,
    ) -> None:
        self.page = page
        self.selectors = selectors
        self.agent_id = agent_id
        self.verify_timeout_ms = verify_timeout_ms
        self.dry_run = dry_run

    def send_text(self, message: PlatformMessage, text: str) -> SendResult:
        if self.dry_run:
            return SendResult(
                request_id="pending",
                merchant_id="default",
                platform=message.platform,
                external_conversation_id=message.external_conversation_id,
                external_message_id=message.external_message_id,
                send_status="skipped_dry_run",
                sent_text=text,
                agent_id=self.agent_id,
                error_code="DRY_RUN",
                error_message="Dry run mode: reply was not filled or sent.",
                metadata={"dry_run": True},
            )

        try:
            self.page.locator(self.selectors.reply_input).fill(text)
            self.page.locator(self.selectors.send_button).click()
            verified = self._verify_sent_text(text)
            if not verified:
                return self._failed_result(message, text, "SEND_NOT_VERIFIED", "Sent text was not found on page.")
            return SendResult(
                request_id="pending",
                merchant_id="default",
                platform=message.platform,
                external_conversation_id=message.external_conversation_id,
                external_message_id=message.external_message_id,
                send_status="success",
                sent_text=text,
                sent_at=datetime.now(),
                agent_id=self.agent_id,
                metadata={"verification": "sent_text_found"},
            )
        except Exception as exc:
            return self._failed_result(message, text, "SEND_EXCEPTION", str(exc))

    def mark_handoff(self, message: PlatformMessage, reason: str) -> SendResult:
        return SendResult(
            request_id="pending",
            merchant_id="default",
            platform=message.platform,
            external_conversation_id=message.external_conversation_id,
            external_message_id=message.external_message_id,
            send_status="handoff",
            agent_id=self.agent_id,
            error_code="HANDOFF_REQUIRED",
            error_message=reason,
        )

    def _verify_sent_text(self, text: str) -> bool:
        try:
            sent_messages = self.page.locator(self.selectors.sent_messages)
            wait_for_timeout = getattr(self.page, "wait_for_timeout", None)
            if callable(wait_for_timeout):
                wait_for_timeout(min(self.verify_timeout_ms, 500))
            expected = self._normalize_text(text)
            for index in range(sent_messages.count()):
                actual = self._normalize_text(sent_messages.nth(index).inner_text())
                if actual == expected:
                    return True
        except Exception:
            return False
        return False

    def _normalize_text(self, text: str) -> str:
        return " ".join(text.split())

    def _failed_result(self, message: PlatformMessage, text: str, code: str, error: str) -> SendResult:
        return SendResult(
            request_id="pending",
            merchant_id="default",
            platform=message.platform,
            external_conversation_id=message.external_conversation_id,
            external_message_id=message.external_message_id,
            send_status="failed",
            sent_text=text,
            agent_id=self.agent_id,
            error_code=code,
            error_message=error,
        )
