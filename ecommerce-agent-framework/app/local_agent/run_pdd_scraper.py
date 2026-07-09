"""CLI entry point for the PDD product scraper.

Usage::

    # With existing browser profile (recommended — keeps login session)
    python -m app.local_agent.run_pdd_scraper --user-data-dir data/browser_profiles/pdd_edge --headed

    # Headless mode (requires login each time, won't work without session)
    python -m app.local_agent.run_pdd_scraper --headed

    # Output to file
    python -m app.local_agent.run_pdd_scraper --output products.json
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import sys

# Fix Windows console encoding for Unicode output
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape products from PDD merchant goods page.")
    parser.add_argument("--user-data-dir", default="", help="Browser user data dir (preserves login)")
    parser.add_argument("--page-url", default="https://mms.pinduoduo.com/goods/goods_list",
                        help="PDD goods management page URL")
    parser.add_argument("--browser-channel", default="msedge")
    parser.add_argument("--headed", action="store_true", help="Show browser window")
    parser.add_argument("--max-pages", type=int, default=3, help="Max pages to scrape")
    parser.add_argument("--output", default="", help="Output JSON file path")
    parser.add_argument("--merchant-id", default="default")
    parser.add_argument("--list-only", action="store_true",
                        help="只抓列表页, 不进入详情页")
    parser.add_argument("--import-to-api", action="store_true",
                        help="Import results into the product management API")
    args = parser.parse_args()

    if args.user_data_dir:
        logger.info("Using browser profile from: %s", args.user_data_dir)
    else:
        logger.warning("No --user-data-dir provided. Login session may be missing.")

    try:
        from app.local_agent.scrapers.pdd_product_scraper import PddProductScraper

        scraper = PddProductScraper(
            user_data_dir=args.user_data_dir,
            page_url=args.page_url,
            browser_channel=args.browser_channel,
        )
        products = scraper.scrape(
            headless=not args.headed,
            max_pages=args.max_pages,
            list_only=args.list_only,
        )

        if not products:
            logger.warning("No products found. The page DOM may differ from expected patterns.")
            print(json.dumps({"status": "empty", "products": [], "count": 0}, ensure_ascii=False, indent=2))
            return

        # Convert to dicts
        product_dicts = []
        for p in products:
            d = {
                "platform_product_id": p.platform_product_id,
                "title": p.title,
                "price": p.price,
                "stock": p.stock,
                "sku": p.sku,
                "category": p.category,
                "image_url": p.image_url,
                "source_url": p.source_url,
                "source_type": "platform_scrape",
                "platform": "pinduoduo",
                "merchant_id": args.merchant_id,
            }
            if p.raw_data:
                d["_raw"] = p.raw_data
            product_dicts.append(d)

        result = {"status": "ok", "count": len(product_dicts), "products": product_dicts}

        output = json.dumps(result, ensure_ascii=False, indent=2)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            logger.info("Written %d products to %s", len(product_dicts), args.output)

        if args.import_to_api:
            _import_via_api(product_dicts)

        print(output)

    except ImportError as exc:
        logger.error("Missing dependency: %s", exc)
        logger.error("Run: pip install playwright && python -m playwright install chromium")
        sys.exit(1)
    except Exception as exc:
        logger.exception("Scraping failed: %s", exc)
        sys.exit(1)


def _import_via_api(products: list) -> None:
    """POST scraped products to the product management API."""
    try:
        import requests
    except ImportError:
        logger.error("requests library required for --import-to-api")
        return

    api_base = "http://localhost:8000"
    ok = 0
    fail = 0
    for p in products:
        payload = {k: v for k, v in p.items() if not k.startswith("_")}
        try:
            resp = requests.post(f"{api_base}/api/products", json=payload, timeout=10)
            if resp.status_code in (200, 201):
                ok += 1
            else:
                logger.warning("API rejected: %s  %s", p.get("title"), resp.text[:200])
                fail += 1
        except requests.ConnectionError:
            logger.error("Cannot connect to API at %s. Is the backend running?", api_base)
            fail += 1
            break
        except Exception as exc:
            logger.warning("API error for %s: %s", p.get("title"), exc)
            fail += 1

    logger.info("Import result: %d imported, %d failed", ok, fail)


if __name__ == "__main__":
    main()
