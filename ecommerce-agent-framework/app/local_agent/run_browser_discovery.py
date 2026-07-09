"""Discover selector candidates for a real web customer-service page."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from app.local_agent.browser.discovery import discover_selectors


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover browser chat selector candidates.")
    parser.add_argument("--page-url", required=True)
    parser.add_argument("--browser-channel", default="msedge")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--user-data-dir", default=None)
    parser.add_argument("--wait-before-scan", type=float, default=20.0)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Python Playwright is not installed. Run: pip install playwright && python -m playwright install chromium"
        ) from exc

    with sync_playwright() as playwright:
        launch_options = {"headless": not args.headed, "channel": args.browser_channel}
        if args.user_data_dir:
            context = playwright.chromium.launch_persistent_context(args.user_data_dir, **launch_options)
            page = context.pages[0] if context.pages else context.new_page()
            closer = context
        else:
            browser = playwright.chromium.launch(**launch_options)
            page = browser.new_page()
            closer = browser

        page.goto(args.page_url)
        if args.wait_before_scan > 0:
            time.sleep(args.wait_before_scan)
        result = discover_selectors(page)

        output = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output_json:
            output_path = Path(args.output_json)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(output, encoding="utf-8")
        print(output)
        closer.close()


if __name__ == "__main__":
    main()
