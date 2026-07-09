"""Generic composable adapter for web-based customer service pages."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.local_agent.adapters.base import PlatformMessage, SendResult
from app.local_agent.executors.base import ReplyExecutor
from app.local_agent.extractors.base import PageContextExtractor
from app.local_agent.store.deduper import EventDeduper
from app.local_agent.store.session_queue import SessionQueue
from app.local_agent.watchers.base import MessageWatcher, RawMessageEvent


class StaticContextExtractor:
    def __init__(self, page_context: Optional[Dict[str, Any]] = None) -> None:
        self.page_context = page_context or {}

    def extract_for_message(self, event: RawMessageEvent) -> Dict[str, Any]:
        return dict(self.page_context)


class GenericWebChatAdapter:
    def __init__(
        self,
        platform: str,
        watcher: MessageWatcher,
        executor: ReplyExecutor,
        context_extractor: Optional[PageContextExtractor] = None,
        deduper: Optional[EventDeduper] = None,
        session_queue: Optional[SessionQueue] = None,
        selector_profile_name: Optional[str] = None,
    ) -> None:
        self.platform = platform
        self.watcher = watcher
        self.executor = executor
        self.context_extractor = context_extractor or StaticContextExtractor()
        self.deduper = deduper or EventDeduper()
        self.session_queue = session_queue or SessionQueue()
        self.selector_profile_name = selector_profile_name

    def detect_app(self) -> bool:
        return self.watcher.detect_app()

    def detect_login_status(self) -> bool:
        return self.watcher.detect_login_status()

    def read_new_messages(self) -> List[PlatformMessage]:
        for event in self.watcher.read_events():
            event_key = self._event_key(event)
            if not self.deduper.is_new(event_key):
                continue
            self.session_queue.push(self._to_platform_message(event))
        return self.session_queue.drain_conversation_serial()

    def send_text(self, message: PlatformMessage, text: str) -> SendResult:
        return self.executor.send_text(message, text)

    def mark_handoff(self, message: PlatformMessage, reason: str) -> SendResult:
        return self.executor.mark_handoff(message, reason)

    def health_check(self) -> Dict[str, Any]:
        watcher_health = self.watcher.health_check()
        return {
            **watcher_health,
            "platform": self.platform,
            "adapter": "GenericWebChatAdapter",
            "queued_messages": self.session_queue.size(),
        }

    def _to_platform_message(self, event: RawMessageEvent) -> PlatformMessage:
        return PlatformMessage(
            platform=self.platform,
            external_conversation_id=event.external_conversation_id,
            external_message_id=event.external_message_id,
            customer_message=event.text,
            observed_at=event.observed_at,
            customer_id=event.customer_id,
            customer_name=event.customer_name,
            page_context=self.context_extractor.extract_for_message(event),
            metadata={
                **event.metadata,
                "raw_platform": event.platform,
                "adapter": "GenericWebChatAdapter",
            },
        )

    def _event_key(self, event: RawMessageEvent) -> str:
        return f"{event.platform}:{event.external_conversation_id}:{event.external_message_id}"
