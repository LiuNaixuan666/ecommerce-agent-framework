"""
Scraper registry — maps platform names to their scraper implementations.

All platform-specific scraper lookups MUST go through this registry.
Business logic MUST NOT hardcode scraper imports for specific platforms.
"""

from __future__ import annotations

import importlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Registry: platform_key -> "module_path.ClassName"
SUPPORTED_PRODUCT_SCRAPERS: dict[str, str] = {
    "pinduoduo": "app.local_agent.scrapers.pdd_product_scraper.PddProductScraper",
}


def get_product_scraper(platform: str):
    """
    Return the scraper *class* for *platform*, or ``None`` if the
    platform has no registered scraper.

    The class is lazy-imported on first access so that heavy dependencies
    (e.g. Playwright) are only loaded when actually needed.
    """
    key = (platform or "").strip().lower()
    dotted_path = SUPPORTED_PRODUCT_SCRAPERS.get(key)
    if not dotted_path:
        return None

    module_path, class_name = dotted_path.rsplit(".", 1)
    try:
        module = importlib.import_module(module_path)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        logger.warning("Could not load scraper %s for platform %s: %s", dotted_path, platform, exc)
        return None


def list_supported_product_scraper_platforms() -> list[str]:
    """Return sorted list of platform keys that have a scraper registered."""
    return sorted(SUPPORTED_PRODUCT_SCRAPERS.keys())


def is_product_scraper_supported(platform: str) -> bool:
    """Quick boolean check — does *platform* have a scraper?"""
    return (platform or "").strip().lower() in SUPPORTED_PRODUCT_SCRAPERS
