"""
Platform browser session API routes.

Provides endpoints for opening platform pages, checking login status,
managing browser sessions, and controlling Local Agent.

All Playwright-dependent calls are dispatched to a thread pool via
``asyncio.to_thread()`` so that the sync Playwright API never collides
with FastAPI's async event loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
import queue
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.local_agent.browser_session_manager import browser_session_manager
from app.local_agent.platforms import (
    get_platform,
    get_platform_page_url,
    is_platform_active,
    list_supported_browser_platforms,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/platform-browser", tags=["platform-browser"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class OpenSessionRequest(BaseModel):
    platform: str = Field(..., min_length=1)
    page_type: str = Field(default="chat", pattern=r"^(login|home|chat|products|orders)$")
    merchant_id: str = Field(default="default")
    shop_id: Optional[str] = None
    profile_id: Optional[str] = None
    headed: bool = Field(default=True)


class CheckLoginRequest(BaseModel):
    platform: str = Field(..., min_length=1)
    page_type: str = Field(default="chat")
    profile_id: Optional[str] = None


class StartAgentRequest(BaseModel):
    platform: str = Field(..., min_length=1)
    page_type: str = Field(default="chat")
    merchant_id: str = Field(default="default")
    shop_id: Optional[str] = None
    profile_id: Optional[str] = None
    mode: str = Field(default="dry_run", pattern=r"^(dry_run|assist|auto)$")
    interval_seconds: float = Field(default=10, ge=2, le=300)


class StopAgentRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)


class PlatformBrowserActionRequest(BaseModel):
    platform: str = Field(..., min_length=1)
    page_type: str = Field(default="chat")
    profile_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Unified error helper
# ---------------------------------------------------------------------------


def _error_response(code: str, message: str) -> Dict[str, Any]:
    return {"ok": False, "error_code": code, "message": message}


def _ok_response(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"ok": True, **data}


# ---------------------------------------------------------------------------
# Dedicated worker for Playwright calls
# ---------------------------------------------------------------------------

import queue


class _PlaywrightWorker:
    """Run all sync Playwright operations on one long-lived thread."""

    def __init__(self) -> None:
        self._jobs: queue.Queue = queue.Queue()
        self._thread = threading.Thread(
            target=self._run,
            name="platform-browser-playwright",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        while True:
            fn, args, kwargs, result_q = self._jobs.get()
            try:
                result_q.put(("ok", fn(*args, **kwargs)))
            except BaseException as exc:
                logger.exception("Playwright worker job failed: %s", exc)
                result_q.put(("error", exc))

    async def call(self, fn, *args, **kwargs):
        result_q: queue.Queue = queue.Queue(maxsize=1)
        self._jobs.put((fn, args, kwargs, result_q))

        while True:
            try:
                status, value = result_q.get_nowait()
                break
            except queue.Empty:
                await asyncio.sleep(0.05)

        if status == "error":
            raise value  # type: ignore[misc]
        return value


_playwright_worker = _PlaywrightWorker()


_browser_agent_lock = threading.Lock()
_browser_agent_runners: Dict[str, Dict[str, Any]] = {}


async def _run_in_thread(fn, *args, **kwargs):
    """Run sync Playwright calls on one dedicated raw worker thread."""
    return await _playwright_worker.call(fn, *args, **kwargs)


def _start_browser_agent_runner(
    *,
    agent_id: str,
    platform: str,
    merchant_id: str,
    mode: str,
    interval_seconds: float,
) -> None:
    stop_event = threading.Event()
    state: Dict[str, Any] = {}

    def runner() -> None:
        while not stop_event.is_set():
            try:
                asyncio.run(
                    _run_in_thread(
                        _browser_agent_cycle,
                        state,
                        agent_id,
                        platform,
                        merchant_id,
                        mode,
                    )
                )
            except Exception as exc:
                logger.exception("Browser agent cycle failed: %s", exc)
                try:
                    from app.storage.rpa_runtime_store import rpa_runtime_store
                    rpa_runtime_store.save_heartbeat({
                        "agent_id": agent_id,
                        "merchant_id": merchant_id,
                        "platform": platform,
                        "status": "error",
                        "error_code": "BROWSER_AGENT_CYCLE_FAILED",
                        "error_message": str(exc),
                    })
                except Exception:
                    pass
            stop_event.wait(interval_seconds)

    with _browser_agent_lock:
        existing = _browser_agent_runners.get(agent_id)
        if existing:
            existing["stop_event"].set()

        thread = threading.Thread(
            target=runner,
            name=f"browser-agent-{agent_id}",
            daemon=True,
        )
        _browser_agent_runners[agent_id] = {
            "thread": thread,
            "stop_event": stop_event,
            "state": state,
        }
        thread.start()


def _stop_browser_agent_runner(agent_id: str) -> bool:
    with _browser_agent_lock:
        runner = _browser_agent_runners.pop(agent_id, None)
    if not runner:
        return False
    runner["stop_event"].set()
    return True


def _browser_agent_cycle(
    state: Dict[str, Any],
    agent_id: str,
    platform: str,
    merchant_id: str,
    mode: str,
) -> Dict[str, Any]:
    from app.local_agent.adapters.browser_web_chat import build_browser_web_chat_adapter
    from app.local_agent.browser.profiles import get_builtin_profile
    from app.local_agent.http_client import LocalBackendClient
    from app.local_agent.runtime import LocalAgentRuntime

    page = browser_session_manager.ensure_page_open(platform, "chat")
    if page is None:
        raise RuntimeError("Chat page is not open and could not be created")

    profile_name = "pinduoduo_web" if platform == "pinduoduo" else "browser_mock"
    profile = get_builtin_profile(profile_name)
    dry_run = mode != "auto"

    if state.get("page") is not page:
        state.clear()
        state["page"] = page
        state["adapter"] = build_browser_web_chat_adapter(
            page=page,
            platform=profile.platform,
            selectors=profile.selectors,
            agent_id=agent_id,
            default_conversation_id=profile.default_conversation_id,
            dry_run=dry_run,
            latest_only=True,
            selector_profile_name=profile.name,
        )
        state["runtime"] = LocalAgentRuntime(agent_id=agent_id, merchant_id=merchant_id)
        state["backend_client"] = LocalBackendClient(
            base_url=os.getenv("LOCAL_AGENT_BACKEND_URL", "http://127.0.0.1:8003")
        )

    adapter = state["adapter"]
    runtime = state["runtime"]
    backend_client = state["backend_client"]
    summary = runtime.process_once(adapter, backend_client)

    session = browser_session_manager.get_session(platform, "chat")
    if session:
        session.status = "running"
        session.logged_in = True
        session.current_url = page.url
        session.page_title = page.title()
        session.last_heartbeat_at = datetime.now().isoformat()
        session.error_message = None

    return summary


def _debug_read_chat_events(platform: str, profile_id: Optional[str] = None) -> Dict[str, Any]:
    from dataclasses import asdict

    from app.local_agent.browser.profiles import get_builtin_profile
    from app.local_agent.watchers.browser_page import BrowserPageWatcher

    page = browser_session_manager.ensure_page_open(platform, "chat", profile_id=profile_id)
    if page is None:
        raise RuntimeError("Chat page is not open and could not be created")

    profile_name = "pinduoduo_web" if platform == "pinduoduo" else "browser_mock"
    profile = get_builtin_profile(profile_name)
    watcher = BrowserPageWatcher(
        page=page,
        platform=profile.platform,
        selectors=profile.selectors,
        default_conversation_id=profile.default_conversation_id,
        latest_only=False,
    )
    events = watcher.read_events()
    return {
        "health": watcher.health_check(),
        "event_count": len(events),
        "events": [asdict(event) for event in events],
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/capabilities")
async def get_capabilities() -> Dict[str, Any]:
    """Return which platforms and page types are available."""
    platforms = []
    for code in sorted(list_supported_browser_platforms()):
        pdef = get_platform(code)
        if pdef is None:
            continue
        pages = list(pdef.get("pages", {}).keys())
        platforms.append({
            "code": code,
            "name": pdef.get("name", code),
            "status": pdef.get("status", "coming_soon"),
            "available_pages": pages,
            "has_scraper": pdef.get("scraper_key") is not None,
            "profile_id": pdef.get("profile_id"),
            "profile_dir": pdef.get("profile_dir"),
        })
    return {"platforms": platforms, "total": len(platforms)}


@router.post("/open")
async def open_session(request: OpenSessionRequest) -> Dict[str, Any]:
    """Open a platform page in the browser.

    If the user is not logged in, the browser will be redirected to the
    platform login page. After login, call ``/check-login`` to navigate
    back to the target page.
    """
    if not is_platform_active(request.platform):
        raise HTTPException(
            status_code=400,
            detail=_error_response(
                "PLATFORM_NOT_ACTIVE",
                f"Platform '{request.platform}' is not active. "
                f"Supported platforms: {list_supported_browser_platforms()}",
            ),
        )

    page_url = get_platform_page_url(request.platform, request.page_type)
    if not page_url:
        raise HTTPException(
            status_code=400,
            detail=_error_response(
                "PAGE_TYPE_NOT_CONFIGURED",
                f"Page type '{request.page_type}' is not configured for '{request.platform}'.",
            ),
        )

    try:
        session = await _run_in_thread(
            browser_session_manager.open_session,
            platform=request.platform,
            page_type=request.page_type,
            merchant_id=request.merchant_id,
            shop_id=request.shop_id,
            profile_id=request.profile_id,
            headed=request.headed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=_error_response("INVALID_REQUEST", str(exc)))
    except Exception as exc:
        logger.exception("Failed to open session: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=_error_response("SESSION_OPEN_FAILED", f"Failed to open session: {exc}"),
        )

    if session.status == "error":
        raise HTTPException(
            status_code=500,
            detail=_error_response(
                "SESSION_OPEN_FAILED",
                session.error_message or "Failed to open browser session",
            ),
        )

    return _ok_response({"session": session.to_dict()})


@router.post("/check-login")
async def check_login(request: CheckLoginRequest) -> Dict[str, Any]:
    """Check login status for an existing browser session."""
    result = await _run_in_thread(
        browser_session_manager.check_login,
        platform=request.platform,
        page_type=request.page_type,
        profile_id=request.profile_id,
    )
    return _ok_response(result)


@router.post("/debug-read-chat")
async def debug_read_chat(request: PlatformBrowserActionRequest) -> Dict[str, Any]:
    """Read parsed chat events from the current browser page for diagnostics."""
    try:
        result = await _run_in_thread(
            _debug_read_chat_events,
            request.platform,
            request.profile_id,
        )
        return _ok_response(result)
    except Exception as exc:
        logger.exception("Debug chat read failed: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=_error_response("DEBUG_READ_CHAT_FAILED", str(exc)),
        )


@router.post("/start-agent")
async def start_agent(request: StartAgentRequest) -> Dict[str, Any]:
    """Start the Local Agent listening loop for a platform session."""
    if request.page_type != "chat":
        raise HTTPException(
            status_code=400,
            detail=_error_response("INVALID_PAGE_TYPE", "AI 接待只能在客服页启动。请先打开客服页。"),
        )

    session = await _run_in_thread(
        browser_session_manager.open_session,
        platform=request.platform,
        page_type=request.page_type,
        merchant_id=request.merchant_id,
        shop_id=request.shop_id,
        profile_id=request.profile_id,
        headed=True,
    )
    if not session:
        raise HTTPException(
            status_code=400,
            detail=_error_response(
                "SESSION_NOT_FOUND",
                f"No open session for {request.platform}/{request.page_type}.",
            ),
        )
    if not session.logged_in:
        raise HTTPException(
            status_code=400,
            detail=_error_response(
                "SESSION_NOT_LOGGED_IN",
                f"Session {session.session_id} is not logged in.",
            ),
        )
    session.status = "running"
    session.last_heartbeat_at = datetime.now().isoformat()
    agent_id = f"{request.platform}-{request.page_type}"
    try:
        from app.storage.agent_rule_store import agent_rule_store

        rules = agent_rule_store.get_rules(merchant_id=request.merchant_id, platform=request.platform)
        rules["mode"] = request.mode
        agent_rule_store.save_rules(rules)
    except Exception as exc:
        logger.warning("Failed to sync agent mode to rule config: %s", exc)
    _start_browser_agent_runner(
        agent_id=agent_id,
        platform=request.platform,
        merchant_id=request.merchant_id,
        mode=request.mode,
        interval_seconds=request.interval_seconds,
    )
    try:
        from app.storage.rpa_runtime_store import rpa_runtime_store
        rpa_runtime_store.save_heartbeat({
            "agent_id": agent_id,
            "merchant_id": request.merchant_id,
            "platform": request.platform,
            "status": "running",
            "current_page_url": session.current_url,
            "watched_window_title": session.page_title,
            "metadata": {
                "mode": request.mode,
                "source": "start-agent",
            },
        })
    except Exception as exc:
        logger.warning("Failed to record initial browser agent heartbeat: %s", exc)
    return _ok_response({
        "agent_id": agent_id,
        "platform": request.platform,
        "mode": request.mode,
        "session": session.to_dict(),
    })


@router.post("/stop-agent")
async def stop_agent(request: StopAgentRequest) -> Dict[str, Any]:
    """Stop a running agent session and close the browser page."""
    sessions = await _run_in_thread(browser_session_manager.list_sessions)
    for s in sessions:
        sid = s.get("session_id", "")
        agent_id = f"{s.get('platform', '')}-{s.get('page_type', '')}"
        if request.agent_id in (sid, agent_id):
            _stop_browser_agent_runner(agent_id)
            try:
                from app.storage.rpa_runtime_store import rpa_runtime_store
                rpa_runtime_store.save_heartbeat({
                    "agent_id": agent_id,
                    "merchant_id": s.get("merchant_id") or "default",
                    "platform": s.get("platform"),
                    "status": "stopped",
                    "current_page_url": s.get("current_url"),
                    "watched_window_title": s.get("page_title"),
                })
            except Exception:
                pass
            await _run_in_thread(
                browser_session_manager.close_session,
                platform=s["platform"],
                page_type=s["page_type"],
                profile_id=s.get("profile_id"),
            )
            return _ok_response({"status": "stopped", "agent_id": request.agent_id})
    raise HTTPException(
        status_code=404,
        detail=_error_response("AGENT_NOT_FOUND", f"No session found for agent_id: {request.agent_id}"),
    )


@router.get("/sessions")
async def list_sessions() -> Dict[str, Any]:
    """List all open browser sessions with their current status."""
    sessions = await _run_in_thread(browser_session_manager.list_sessions)
    return {"sessions": sessions, "total": len(sessions)}


@router.post("/focus")
async def focus_page(request: PlatformBrowserActionRequest) -> Dict[str, Any]:
    """Bring a browser page to front (best-effort)."""
    ok = await _run_in_thread(
        browser_session_manager.focus_page,
        platform=request.platform,
        page_type=request.page_type,
        profile_id=request.profile_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail=_error_response("PAGE_NOT_FOUND", "No open page"))
    return _ok_response({"status": "focused"})


@router.post("/refresh")
async def refresh_page(request: PlatformBrowserActionRequest) -> Dict[str, Any]:
    """Refresh a browser page."""
    ok = await _run_in_thread(
        browser_session_manager.refresh_page,
        platform=request.platform,
        page_type=request.page_type,
        profile_id=request.profile_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail=_error_response("PAGE_NOT_FOUND", "No open page"))
    return _ok_response({"status": "refreshed"})


@router.post("/close")
async def close_page(request: PlatformBrowserActionRequest) -> Dict[str, Any]:
    """Close a browser page/tab for the given platform+page_type."""
    ok = await _run_in_thread(
        browser_session_manager.close_session,
        platform=request.platform,
        page_type=request.page_type,
        profile_id=request.profile_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail=_error_response("PAGE_NOT_FOUND", "No open page"))
    return _ok_response({"status": "closed"})
