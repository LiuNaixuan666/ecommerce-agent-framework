"""
Browser session manager — manages Playwright browser sessions per platform.

Core principle: one persistent browser context per ``(platform, profile_id)``
pair.  Multiple pages (chat, products, login) live inside the same context so
they share cookies, localStorage, and login state without profile-lock conflicts.
"""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


from app.local_agent.platforms import (
    get_platform,
    get_platform_page_url,
    get_platform_login_page_type,
    get_platform_target_after_login,
    is_platform_active,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model — one handle per profile, one session per page
# ---------------------------------------------------------------------------


@dataclass
class BrowserPageSession:
    """Represents a single page/tab within a shared browser context."""

    session_id: str                           # composite: platform:page_type:profile_id
    platform: str
    page_type: str                            # login | home | chat | products | orders
    profile_id: str
    merchant_id: str = "default"
    shop_id: Optional[str] = None

    # Runtime state
    status: str = "not_opened"                # not_opened | opening | login_required | ready | running | paused | error
    logged_in: bool = False
    current_url: Optional[str] = None
    page_title: Optional[str] = None
    last_heartbeat_at: Optional[str] = None
    error_message: Optional[str] = None
    target_after_login: Optional[str] = None  # page_type to navigate to after successful login

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "platform": self.platform,
            "page_type": self.page_type,
            "profile_id": self.profile_id,
            "merchant_id": self.merchant_id,
            "shop_id": self.shop_id,
            "status": self.status,
            "logged_in": self.logged_in,
            "current_url": self.current_url,
            "page_title": self.page_title,
            "last_heartbeat_at": self.last_heartbeat_at,
            "error_message": self.error_message,
            "target_after_login": self.target_after_login,
        }


@dataclass
class _BrowserContextHandle:
    """Internal handle for a shared Playwright persistent context."""

    context_key: str                          # platform:profile_id
    platform: str
    profile_id: str
    profile_dir: str

    playwright: Any = None
    context: Any = None
    pages: Dict[str, Any] = field(default_factory=dict)   # page_type -> page
    sessions: Dict[str, BrowserPageSession] = field(default_factory=dict)
    last_used_at: Optional[str] = None
    error: Optional[str] = None
    _lock: threading.Lock = field(default_factory=threading.Lock)


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class BrowserSessionManager:
    """Manages persistent browser contexts and page sessions.

    Thread-safe.
    """

    def __init__(self) -> None:
        self._contexts: Dict[str, _BrowserContextHandle] = {}
        self._lock = threading.Lock()

    # ---- Public API ----

    def open_session(
        self,
        platform: str,
        page_type: str,
        merchant_id: str = "default",
        shop_id: Optional[str] = None,
        profile_id: Optional[str] = None,
        headed: bool = True,
    ) -> BrowserPageSession:
        """Open (or reuse) a browser page for the given platform + page_type.

        Returns the existing session if one is already open for the same
        composite key.  If the browser context for the profile does not exist yet,
        it is created once and reused for all subsequent page_types.
        """
        if not is_platform_active(platform):
            raise ValueError(f"Platform '{platform}' is not active / supported")

        platform_def = get_platform(platform)
        if not platform_def:
            raise ValueError(f"Unknown platform: {platform}")

        if not profile_id:
            profile_id = platform_def.get("profile_id", f"{platform}_edge")

        context_key = f"{platform}:{profile_id}"
        session_id = f"{context_key}:{page_type}"

        stale_handle: Optional[_BrowserContextHandle] = None

        # Reuse existing session if still alive
        with self._lock:
            for handle in list(self._contexts.values()):
                if handle.context_key == context_key:
                    existing = handle.sessions.get(session_id)
                    if existing and existing.current_url is not None:
                        # Check if the page is still alive (user didn't close the window)
                        page = handle.pages.get(page_type)
                        if page is not None and self._is_page_alive(page):
                            return existing
                        elif page is not None:
                            # Page was closed — recreate it
                            logger.info("Page %s was closed; recreating", session_id)
                            try:
                                if not self._is_context_alive(handle.context):
                                    raise RuntimeError("browser context is closed")
                                new_page = handle.context.new_page()
                                handle.pages[page_type] = new_page
                                new_page.goto(get_platform_page_url(platform, page_type) or "about:blank",
                                              wait_until="domcontentloaded", timeout=30000)
                                existing.current_url = new_page.url
                                existing.page_title = self._safe_page_title(new_page)
                                existing.error_message = None
                                self._check_login(existing, new_page)
                                return existing
                            except Exception as exc:
                                logger.warning("Failed to recreate page %s: %s", session_id, exc)
                                stale_handle = handle
                                self._contexts.pop(context_key, None)
                                break

        if stale_handle is not None:
            self._close_context_resources(stale_handle)

        # Get or create the shared context handle
        handle = self._get_or_create_context(platform, profile_id, platform_def, headed)
        if handle.error:
            session = BrowserPageSession(
                session_id=session_id,
                platform=platform,
                page_type=page_type,
                profile_id=profile_id,
                merchant_id=merchant_id,
                shop_id=shop_id,
                status="error",
                error_message=handle.error,
            )
            with self._lock:
                handle.sessions[session_id] = session
            return session

        # Create a new page in the existing context
        session = self._create_page_session(handle, platform, page_type, profile_id, merchant_id, shop_id)

        # Login fallback
        url = get_platform_page_url(platform, page_type)
        if not url:
            session.status = "error"
            session.error_message = f"No URL configured for platform={platform} page_type={page_type}"
            return session

        try:
            page = handle.pages.get(page_type)
            if page is None:
                page = self._claim_reusable_page(handle, page_type)
            if page is None:
                page = handle.context.new_page()
                handle.pages[page_type] = page

            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            session.current_url = self._safe_page_url(page)
            session.page_title = self._safe_page_title(page)
            session.last_heartbeat_at = datetime.now().isoformat()

            # Wait for SPA to finish rendering before checking login
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            import time
            time.sleep(1.5)

            # Check login status and redirect to login if needed
            self._check_login(session, page)
            if not session.logged_in and page_type != "login":
                login_page_type = get_platform_login_page_type(platform) or "login"
                login_url = get_platform_page_url(platform, login_page_type)
                if login_url:
                    logger.info("Not logged in; navigating %s to login page %s", session_id, login_url)
                    page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
                    session.current_url = self._safe_page_url(page)
                    session.page_title = self._safe_page_title(page)
                    session.target_after_login = page_type
                    session.status = "login_required"
                else:
                    session.status = "login_required"
            elif session.logged_in and session.target_after_login:
                # Navigate back to original target after login
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                session.current_url = self._safe_page_url(page)
                session.page_title = self._safe_page_title(page)
                session.target_after_login = None
                session.status = "ready"

        except Exception as exc:
            logger.exception("Failed to open page %s: %s", url, exc)
            session.status = "error"
            session.error_message = str(exc)
            if self._is_closed_target_error(exc):
                self._destroy_context(handle)

        return session

    def check_login(self, platform: str, page_type: str, profile_id: Optional[str] = None) -> Dict[str, Any]:
        """Check login status for an existing session."""
        session, handle = self._find_session_and_handle(platform, page_type, profile_id)
        if not session:
            session = self.open_session(platform, page_type, profile_id=profile_id)
            _, handle = self._find_session_and_handle(platform, page_type, profile_id)

        page = handle.pages.get(page_type) if handle else None
        if page is None or not self._is_page_alive(page):
            page = self.ensure_page_open(platform, page_type, profile_id=profile_id)

        if page is None:
            return {
                "platform": platform,
                "logged_in": False,
                "status": "not_opened",
                "current_url": None,
                "page_title": None,
                "reason": "Page was closed and could not be reopened",
            }

        # Wait for SPA rendering
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass
        import time
        time.sleep(1.5)

        self._check_login(session, page)

        # If now logged in and has a pending target after login, navigate there
        if session.logged_in and session.target_after_login:
            target_url = get_platform_page_url(platform, session.target_after_login)
            if target_url:
                try:
                    page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                    session.current_url = self._safe_page_url(page)
                    session.page_title = self._safe_page_title(page)
                    session.target_after_login = None
                except Exception as exc:
                    logger.warning("Failed to navigate after login: %s", exc)

        return {
            "platform": platform,
            "logged_in": session.logged_in,
            "status": session.status,
            "current_url": session.current_url,
            "page_title": session.page_title,
            "reason": None if session.logged_in else "Not logged in or not detected as ready",
        }

    def close_session(self, platform: str, page_type: str, profile_id: Optional[str] = None) -> bool:
        """Close a specific page/tab for the given platform+page_type.

        The underlying browser context is kept alive until all sessions for
        that profile are closed.
        """
        session, handle = self._find_session_and_handle(platform, page_type, profile_id)
        if not session or not handle:
            return False

        with handle._lock:
            page = handle.pages.pop(page_type, None)
            session_obj = handle.sessions.pop(session.session_id, None)
            if page is not None:
                try:
                    page.close()
                except Exception as exc:
                    logger.warning("Error closing page %s: %s", session.session_id, exc)

            # If no more pages, close the entire context
            if not handle.pages:
                self._destroy_context(handle)

        return True

    def close_all_sessions(self) -> None:
        """Close all browser contexts and clean up."""
        with self._lock:
            handles = list(self._contexts.values())
            self._contexts.clear()
        for handle in handles:
            self._destroy_context(handle)

    def focus_page(self, platform: str, page_type: str, profile_id: Optional[str] = None) -> bool:
        """Bring a page to the front (not always possible in headed mode)."""
        session, handle = self._find_session_and_handle(platform, page_type, profile_id)
        if not session or not handle:
            return False
        page = handle.pages.get(page_type)
        if page is None:
            return False
        try:
            page.bring_to_front()
            return True
        except Exception:
            return False

    def refresh_page(self, platform: str, page_type: str, profile_id: Optional[str] = None) -> bool:
        """Refresh a page."""
        session, handle = self._find_session_and_handle(platform, page_type, profile_id)
        if not session or not handle:
            return False
        page = handle.pages.get(page_type)
        if page is None:
            return False
        try:
            page.reload(wait_until="domcontentloaded", timeout=30000)
            session.current_url = page.url
            session.page_title = self._safe_page_title(page)
            return True
        except Exception as exc:
            logger.warning("Error refreshing page %s: %s", session.session_id, exc)
            return False

    def list_sessions(self) -> List[Dict[str, Any]]:
        """Return a list of all session status dicts."""
        with self._lock:
            result = []
            for handle in self._contexts.values():
                # Update URL/title for active pages
                for page_type, page in list(handle.pages.items()):
                    try:
                        url = page.url
                        title = self._safe_page_title(page)
                        session = handle.sessions.get(f"{handle.context_key}:{page_type}")
                        if session:
                            session.current_url = url
                            session.page_title = title
                            session.last_heartbeat_at = datetime.now().isoformat()
                    except Exception:
                        pass
                for session in handle.sessions.values():
                    result.append(session.to_dict())
            return result

    def get_session(self, platform: str, page_type: str, profile_id: Optional[str] = None) -> Optional[BrowserPageSession]:
        session, _ = self._find_session_and_handle(platform, page_type, profile_id)
        return session

    def get_page(self, platform: str, page_type: str, profile_id: Optional[str] = None) -> Any:
        """Get the Playwright page object for a session (internal use by Agent)."""
        _, handle = self._find_session_and_handle(platform, page_type, profile_id)
        if handle is None:
            return None
        return handle.pages.get(page_type)

    # ---- Internal helpers ----

    def _get_or_create_context(
        self,
        platform: str,
        profile_id: str,
        platform_def: Dict[str, Any],
        headed: bool,
    ) -> _BrowserContextHandle:
        context_key = f"{platform}:{profile_id}"
        stale_handle: Optional[_BrowserContextHandle] = None

        with self._lock:
            existing = self._contexts.get(context_key)
            if existing is not None:
                # If the existing handle's context is dead, destroy it
                # and create a fresh one.
                if not BrowserSessionManager._is_context_alive(existing.context):
                    logger.warning("Context %s is dead; removing and recreating", context_key)
                    stale_handle = self._contexts.pop(context_key, None)
                else:
                    return existing

            handle = _BrowserContextHandle(
                context_key=context_key,
                platform=platform,
                profile_id=profile_id,
                profile_dir=platform_def.get("profile_dir", ""),
            )
            self._contexts[context_key] = handle

        if stale_handle is not None:
            self._close_context_resources(stale_handle)

        # Lazy-import Playwright outside the lock
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            handle.error = "Playwright is not installed. Run: pip install playwright && python -m playwright install chromium"
            return handle

        profile_dir = handle.profile_dir
        if not profile_dir:
            handle.error = "No profile_dir configured for this platform"
            return handle

        if not os.path.isdir(profile_dir):
            logger.warning("Profile directory %s does not exist; creating", profile_dir)
            os.makedirs(profile_dir, exist_ok=True)

        # Kill any orphaned Edge/Chromium processes holding this profile
        _kill_orphaned_browser_processes(profile_dir)

        # Clean up stale lock files before launching (leftover from crashes)
        for lock_file in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            lock_path = os.path.join(profile_dir, lock_file)
            if os.path.exists(lock_path):
                try:
                    os.remove(lock_path)
                    logger.info("Removed stale lock file: %s", lock_path)
                except Exception as exc:
                    logger.warning("Could not remove lock file %s: %s", lock_path, exc)

        # Platform config can force a browser channel. If omitted, keep the
        # legacy profile-name inference for existing platform definitions.
        if "browser_channel" in platform_def:
            browser_channel = platform_def.get("browser_channel") or None
        else:
            browser_channel = None
            profile_path_lower = profile_dir.lower()
            if "msedge" in profile_path_lower or "edge" in profile_path_lower:
                browser_channel = "msedge"
            elif "chrome" in profile_path_lower:
                browser_channel = "chrome"

        try:
            pw = sync_playwright().start()
            launch_args = {
                "user_data_dir": profile_dir,
                "headless": not headed,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                ],
            }
            if browser_channel:
                launch_args["channel"] = browser_channel

            context = pw.chromium.launch_persistent_context(**launch_args)
            handle.playwright = pw
            handle.context = context
        except Exception as exc:
            logger.exception("Failed to launch persistent context: %s", exc)
            # Clean up handle
            try:
                if handle.playwright:
                    handle.playwright.stop()
            except Exception:
                pass
            with self._lock:
                self._contexts.pop(context_key, None)
            handle.error = str(exc)

        return handle

    def _create_page_session(
        self,
        handle: _BrowserContextHandle,
        platform: str,
        page_type: str,
        profile_id: str,
        merchant_id: str,
        shop_id: Optional[str],
    ) -> BrowserPageSession:
        session_id = f"{handle.context_key}:{page_type}"
        session = BrowserPageSession(
            session_id=session_id,
            platform=platform,
            page_type=page_type,
            profile_id=profile_id,
            merchant_id=merchant_id,
            shop_id=shop_id,
            status="opening",
        )
        with self._lock:
            handle.sessions[session_id] = session
        return session

    def _claim_reusable_page(self, handle: _BrowserContextHandle, page_type: str) -> Any:
        """Reuse an existing unclaimed page to avoid piling up tabs."""
        try:
            claimed = set(handle.pages.values())
            for page in list(handle.context.pages):
                if page in claimed or not self._is_page_alive(page):
                    continue
                handle.pages[page_type] = page
                return page
        except Exception:
            return None
        return None

    def _close_duplicate_startup_pages(self, handle: _BrowserContextHandle) -> None:
        """Close restored startup tabs from the persistent profile when possible."""
        try:
            pages = list(handle.context.pages)
            for page in pages[1:]:
                if not self._is_page_alive(page):
                    continue
                try:
                    page.close()
                except Exception:
                    pass
        except Exception:
            pass

    def _close_context_resources(self, handle: _BrowserContextHandle) -> None:
        """Close Playwright resources without mutating the context registry."""
        try:
            if handle.context is not None:
                handle.context.close()
        except Exception as exc:
            logger.warning("Error closing context: %s", exc)
        try:
            if handle.playwright is not None:
                handle.playwright.stop()
        except Exception as exc:
            logger.warning("Error stopping playwright: %s", exc)

    def _destroy_context(self, handle: _BrowserContextHandle) -> None:
        """Close and clean up a browser context handle."""
        self._close_context_resources(handle)
        with self._lock:
            self._contexts.pop(handle.context_key, None)

    def _find_session_and_handle(
        self,
        platform: str,
        page_type: str,
        profile_id: Optional[str] = None,
    ) -> (Optional[BrowserPageSession], Optional[_BrowserContextHandle]):
        with self._lock:
            for handle in self._contexts.values():
                if handle.platform != platform:
                    continue
                if profile_id is not None and handle.profile_id != profile_id:
                    continue
                session_id = f"{handle.context_key}:{page_type}"
                session = handle.sessions.get(session_id)
                if session:
                    return session, handle
                # If we found a handle but no specific session, return the handle
                # for creating a new page
                return None, handle
        return None, None

    def _check_login(self, session: BrowserPageSession, page: Any) -> None:
        """Update session.logged_in and .status based on current page state."""
        try:
            url = (page.url or "").lower()
            title = (self._safe_page_title(page) or "").lower()
            session.current_url = self._safe_page_url(page)
            session.page_title = self._safe_page_title(page)

            # Login page detection
            login_indicators = ["/login", "登录", "signin", "login", "扫码"]
            if any(ind in url for ind in login_indicators):
                session.logged_in = False
                session.status = "login_required"
                return

            if any(ind in title for ind in ["登录", "login", "signin"]):
                session.logged_in = False
                session.status = "login_required"
                return

            # Chat page detection
            if session.page_type == "chat":
                try:
                    has_reply_input = page.query_selector("#replyTextarea") is not None
                    has_send_btn = page.query_selector("div.send-btn") is not None
                    if has_reply_input or has_send_btn:
                        session.logged_in = True
                        session.status = "ready"
                        return
                    # Check if still connecting
                    body_text = page.inner_text("body")[:200] if page else ""
                    if "连接" in body_text and "服务器" in body_text:
                        session.logged_in = False
                        session.status = "login_required"
                        return
                except Exception:
                    pass

            # Products page detection
            if session.page_type == "products":
                try:
                    body_text = page.inner_text("body")[:500] if page else ""
                    goods_indicators = ["商品列表", "商品管理", "发布商品", "goods"]
                    if any(ind in body_text for ind in goods_indicators):
                        session.logged_in = True
                        session.status = "ready"
                        return
                except Exception:
                    pass

            # Fallback: if we reach here, assume logged in for mms.pinduoduo.com non-login pages
            if "mms.pinduoduo.com" in url and not any(ind in url for ind in login_indicators):
                session.logged_in = True
                session.status = "ready"
                return

            session.logged_in = False
            session.status = "login_required"

        except Exception as exc:
            logger.warning("Login check failed for %s: %s", session.session_id, exc)
            session.logged_in = False
            session.status = "error"
            session.error_message = str(exc)


    # ------------------------------------------------------------------
    # Page / context health checks
    # ------------------------------------------------------------------

    @staticmethod
    def _is_page_alive(page: Any) -> bool:
        """Check if a Playwright page object is still usable."""
        try:
            if hasattr(page, "is_closed") and page.is_closed():
                return False
            _ = page.url
            return True
        except Exception:
            return False

    @staticmethod
    def _safe_page_url(page: Any) -> Optional[str]:
        try:
            return page.url
        except Exception:
            return None

    @staticmethod
    def _safe_page_title(page: Any) -> Optional[str]:
        try:
            return page.title()
        except Exception:
            return None

    @staticmethod
    def _is_context_alive(context: Any) -> bool:
        """Check if a Playwright browser context is still usable."""
        if context is None:
            return False
        try:
            browser = getattr(context, "browser", None)
            if browser is not None and hasattr(browser, "is_connected") and not browser.is_connected():
                return False
            _ = context.pages
            return True
        except Exception:
            return False

    @staticmethod
    def _is_closed_target_error(exc: BaseException) -> bool:
        message = str(exc).lower()
        return (
            "target page, context or browser has been closed" in message
            or "browser has been closed" in message
            or "context has been closed" in message
        )

    @staticmethod
    def _is_browser_alive(handle: _BrowserContextHandle) -> bool:
        """Check if the underlying browser process is still alive."""
        if handle is None:
            return False
        if handle.context is None:
            return False
        if not BrowserSessionManager._is_context_alive(handle.context):
            return False
        try:
            _ = handle.context.browser  # Access browser property
            return True
        except Exception:
            return False

    def ensure_page_open(self, platform: str, page_type: str, profile_id: Optional[str] = None,
                         headed: bool = True) -> Optional[Any]:
        """Ensure a page exists and is alive for the given platform+page_type.

        Returns the page object, or None if it cannot be created.
        """
        session, handle = self._find_session_and_handle(platform, page_type, profile_id)
        if handle is None or not self._is_context_alive(handle.context):
            # Need to recreate everything
            session_obj = self.open_session(platform, page_type, headed=headed)
            _, new_handle = self._find_session_and_handle(platform, page_type, profile_id)
            if new_handle is None:
                return None
            return new_handle.pages.get(page_type)

        page = handle.pages.get(page_type) if handle else None
        if page is not None and self._is_page_alive(page):
            return page

        # Page is dead, create a new one in the existing context
        try:
            new_page = self._claim_reusable_page(handle, page_type)
            if new_page is None:
                new_page = handle.context.new_page()
            handle.pages[page_type] = new_page
            if session:
                session.current_url = None
                session.page_title = None
                session.error_message = None
            platform_def = get_platform(platform)
            if platform_def:
                url = get_platform_page_url(platform, page_type)
                if url:
                    new_page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    if session:
                        session.current_url = new_page.url
                        session.page_title = self._safe_page_title(new_page)
                        self._check_login(session, new_page)
            return new_page
        except Exception as exc:
            logger.warning("Failed to create new page for %s/%s: %s", platform, page_type, exc)
            self._destroy_context(handle)
            try:
                session_obj = self.open_session(platform, page_type, profile_id=profile_id, headed=headed)
                if session_obj.status == "error":
                    return None
                _, new_handle = self._find_session_and_handle(platform, page_type, profile_id)
                return new_handle.pages.get(page_type) if new_handle else None
            except Exception as retry_exc:
                logger.warning("Failed to recreate context for %s/%s: %s", platform, page_type, retry_exc)
                return None


# Module-level singleton
browser_session_manager = BrowserSessionManager()


def _kill_orphaned_browser_processes(profile_dir: str) -> None:
    """Kill any Edge/Chromium processes that hold a lock on *profile_dir*.

    These are typically orphaned child processes (crashpad, gpu, renderer)
    left behind after a Playwright browser crash or abnormal exit.  They
    keep ``SingletonLock`` and prevent a new browser from launching.
    """
    if not profile_dir or not os.path.isdir(profile_dir):
        return

    import subprocess

    profile_normalized = os.path.normcase(os.path.normpath(profile_dir))

    try:
        # WMIC query: find edge/chrome processes whose command line contains
        # the profile directory.
        result = subprocess.run(
            [
                "wmic", "process", "where",
                'name="msedge.exe" or name="chrome.exe"',
                "get", "processid,commandline", "/format:csv",
            ],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if profile_normalized in os.path.normcase(line):
                parts = line.split(",")
                if len(parts) >= 2:
                    try:
                        pid = int(parts[-1].strip())
                        if pid > 0:
                            subprocess.run(
                                ["taskkill", "/F", "/PID", str(pid)],
                                capture_output=True, timeout=5,
                            )
                            logger.info("Killed orphaned browser process PID %d", pid)
                    except (ValueError, OSError):
                        pass
    except Exception as exc:
        logger.debug("Failed to clean orphaned browser processes: %s", exc)

