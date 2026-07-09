"""Factory helpers for browser-backed web chat adapters."""

from __future__ import annotations

from typing import Any, Optional

from app.local_agent.adapters.generic_web_chat import GenericWebChatAdapter
from app.local_agent.browser.selectors import BrowserChatSelectors
from app.local_agent.executors.browser_page import BrowserPageReplyExecutor
from app.local_agent.extractors.browser_page import BrowserPageContextExtractor
from app.local_agent.watchers.browser_page import BrowserPageWatcher


def build_browser_web_chat_adapter(
    *,
    page: Any,
    platform: str,
    selectors: BrowserChatSelectors,
    agent_id: str = "local-agent-browser",
    default_conversation_id: str = "browser-conversation",
    dry_run: bool = False,
    latest_only: bool = True,
    selector_profile_name: Optional[str] = None,
) -> GenericWebChatAdapter:
    watcher = BrowserPageWatcher(
        page=page,
        platform=platform,
        selectors=selectors,
        default_conversation_id=default_conversation_id,
        latest_only=latest_only,
    )
    extractor = BrowserPageContextExtractor(page=page, selectors=selectors)
    executor = BrowserPageReplyExecutor(page=page, selectors=selectors, agent_id=agent_id, dry_run=dry_run)
    return GenericWebChatAdapter(
        platform=platform,
        watcher=watcher,
        context_extractor=extractor,
        executor=executor,
        selector_profile_name=selector_profile_name,
    )
