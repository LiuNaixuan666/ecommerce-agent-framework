"""
CLI entry point for isolated subprocess scraping.

Called by ``routes_products._run_scrape`` via ``subprocess`` so that Playwright's
sync API runs in a completely independent Python process, free from any asyncio
event loop detection.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import shutil
import time
import logging

logger = logging.getLogger(__name__)


def _clean_lock_files(profile_dir: str) -> None:
    for lf in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        lp = os.path.join(profile_dir, lf)
        if os.path.exists(lp):
            try:
                os.remove(lp)
            except Exception:
                pass


def list_only(profile_dir: str | None, max_pages: int, output_file: str) -> None:
    """Scrape the product list page and write results to *output_file* as JSON.

    Retries up to 3 times on failure, cleaning lock files between attempts.
    """
    from app.local_agent.scrapers.pdd_product_scraper import PddProductScraper

    ud = profile_dir
    temp_dir = None
    if not ud:
        temp_dir = tempfile.mkdtemp(prefix="pdd_cli_")
        ud = temp_dir
    else:
        _clean_lock_files(ud)

    products = None
    last_error = None
    try:
        for attempt in range(3):
            try:
                scraper = PddProductScraper(user_data_dir=ud)
                products = scraper.scrape(headless=True, max_pages=max_pages, list_only=True)
                scraper.close()
                if products:
                    break
            except Exception as exc:
                last_error = str(exc)
                logger.warning("Scrape attempt %d failed: %s", attempt + 1, last_error)
                if ud:
                    _clean_lock_files(ud)
                time.sleep(2)
                if attempt == 1:
                    import subprocess
                    try:
                        subprocess.run(
                            ["powershell", "-Command",
                             "Get-CimInstance Win32_Process -Filter \"name='msedge.exe'\" | "
                             "Where-Object { $_.CommandLine -match 'pdd_edge' } | "
                             "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                            capture_output=True, timeout=15,
                        )
                    except Exception:
                        pass
                    time.sleep(2)
    finally:
        if temp_dir:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    if not products:
        result = {"error": last_error, "products": []}
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False)
        return

    product_list = []
    for p in products:
        product_list.append({
            "platform_product_id": p.platform_product_id,
            "title": p.title,
            "price": p.price,
            "stock": p.stock,
            "sku": p.sku,
            "category": p.category,
            "description": (p.description or "")[:500],
            "image_url": p.image_url,
            "status": p.status,
        })

    result = {"error": None, "products": product_list}
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--profile-dir", default=None)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    list_only(profile_dir=args.profile_dir, max_pages=args.max_pages, output_file=args.output)
