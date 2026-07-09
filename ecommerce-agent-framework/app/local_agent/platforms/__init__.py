"""
Platform registry — centralised configuration for all supported platforms.

Every platform must have an entry here.  Business logic MUST NOT hardcode
platform URLs, profile paths, or scraper names — look them up through this
registry instead.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Internal data
# ---------------------------------------------------------------------------

def _project_root() -> str:
    """Return the project root (ecommerce-agent-framework/)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _profiles_dir() -> str:
    return os.path.join(_project_root(), "data", "browser_profiles")


# ---------------------------------------------------------------------------
# Platform definitions
# ---------------------------------------------------------------------------

PLATFORMS: Dict[str, Dict[str, Any]] = {
    "pinduoduo": {
        "code": "pinduoduo",
        "name": "拼多多",
        "icon": "pdd",
        "color": "#E02E24",
        "order": 1,
        "status": "active",           # active | beta | coming_soon
        "description": "拼多多商家客服工作台",
        "profile_id": "pdd_chromium",
        "profile_dir": os.path.join(_profiles_dir(), "pdd_chromium"),
        "browser_channel": None,
        "pages": {
            "login": {
                "url": "https://mms.pinduoduo.com/login/",
            },
            "home": {
                "url": "https://mms.pinduoduo.com/home/",
            },
            "chat": {
                "url": "https://mms.pinduoduo.com/chat-merchant/index.html",
                "selector_profile": "pinduoduo_web",
            },
            "products": {
                "url": "https://mms.pinduoduo.com/goods/index.html",
                "scraper": "PddProductScraper",
            },
        },
        "scraper_key": "pinduoduo",
        "login_page_type": "login",
        "target_after_login": "home",
    },
    "xianyu": {
        "code": "xianyu",
        "name": "闲鱼",
        "icon": "xianyu",
        "color": "#FF6A00",
        "order": 2,
        "status": "coming_soon",
        "description": "闲鱼平台客服（即将接入）",
        "profile_id": "xianyu_edge",
        "profile_dir": os.path.join(_profiles_dir(), "xianyu_edge"),
        "pages": {},
        "scraper_key": None,
    },
    "taobao": {
        "code": "taobao",
        "name": "淘宝 / 千牛",
        "icon": "taobao",
        "color": "#FF4400",
        "order": 3,
        "status": "coming_soon",
        "description": "淘宝 / 千牛卖家工作台（即将接入）",
        "profile_id": "taobao_edge",
        "profile_dir": os.path.join(_profiles_dir(), "taobao_edge"),
        "pages": {},
        "scraper_key": None,
    },
    "jd": {
        "code": "jd",
        "name": "京东",
        "icon": "jd",
        "color": "#E2231A",
        "order": 4,
        "status": "coming_soon",
        "description": "京东商家客服（即将接入）",
        "profile_id": "jd_edge",
        "profile_dir": os.path.join(_profiles_dir(), "jd_edge"),
        "pages": {},
        "scraper_key": None,
    },
    "douyin": {
        "code": "douyin",
        "name": "抖店",
        "icon": "douyin",
        "color": "#000000",
        "order": 5,
        "status": "coming_soon",
        "description": "抖音电商客服（即将接入）",
        "profile_id": "douyin_edge",
        "profile_dir": os.path.join(_profiles_dir(), "douyin_edge"),
        "pages": {},
        "scraper_key": None,
    },
}


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------

_ACTIVE_CACHE: Optional[List[Dict[str, Any]]] = None


def get_platform(platform_code: str) -> Optional[Dict[str, Any]]:
    """Return the full platform definition dict, or None."""
    return PLATFORMS.get(platform_code)


def get_active_platforms() -> List[Dict[str, Any]]:
    """Return all platforms that have status != 'coming_soon'."""
    return [p for p in PLATFORMS.values() if p.get("status") != "coming_soon"]


def get_platform_page_url(platform_code: str, page_type: str) -> Optional[str]:
    """Return the URL for a given page type on a given platform."""
    platform = get_platform(platform_code)
    if not platform:
        return None
    page = platform.get("pages", {}).get(page_type)
    if not page:
        return None
    return page.get("url")


def get_platform_selector_profile(platform_code: str) -> Optional[str]:
    """Return the selector profile name for a platform's chat page."""
    platform = get_platform(platform_code)
    if not platform:
        return None
    chat_page = platform.get("pages", {}).get("chat")
    if not chat_page:
        return None
    return chat_page.get("selector_profile")


def get_platform_scraper_key(platform_code: str) -> Optional[str]:
    """Return the scraper registry key for the given platform, or None."""
    platform = get_platform(platform_code)
    if not platform:
        return None
    return platform.get("scraper_key")


def get_platform_login_page_type(platform_code: str) -> Optional[str]:
    """Return the page_type entry for the login page of a platform."""
    platform = get_platform(platform_code)
    if not platform:
        return None
    return platform.get("login_page_type")


def get_platform_target_after_login(platform_code: str) -> Optional[str]:
    """Return the default target page type to navigate to after login."""
    platform = get_platform(platform_code)
    if not platform:
        return None
    return platform.get("target_after_login")


def is_platform_active(platform_code: str) -> bool:
    """Quick boolean — is the platform ready for use?"""
    p = get_platform(platform_code)
    return p is not None and p.get("status") == "active"


def list_supported_browser_platforms() -> List[str]:
    """Return platform codes that have at least one page URL configured."""
    return sorted(
        code for code, p in PLATFORMS.items()
        if p.get("pages") and p.get("status") == "active"
    )
