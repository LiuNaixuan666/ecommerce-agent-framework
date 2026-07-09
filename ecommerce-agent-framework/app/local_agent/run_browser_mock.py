"""Run the browser-backed mock chat adapter with Python Playwright.

This command is optional and requires the Python Playwright package:
    pip install playwright
    python -m playwright install chromium
"""

from __future__ import annotations

import argparse
import json
import time

from app.local_agent.adapters.browser_web_chat import build_browser_web_chat_adapter
from app.local_agent.browser.profiles import get_builtin_profile, load_profile_from_json
from app.local_agent.http_client import LocalBackendClient
from app.local_agent.loop import LocalAgentLoop
from app.local_agent.runtime import LocalAgentRuntime


def main() -> None:
    parser = argparse.ArgumentParser(description="Run browser-backed mock Local Agent.")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--agent-id", default="local-agent-browser-mock")
    parser.add_argument("--merchant-id", default="browser_mock_merchant")
    parser.add_argument("--page-url", default=None)
    parser.add_argument("--profile", default="browser_mock", help="Built-in browser selector profile name.")
    parser.add_argument(
        "--selector-profile-json",
        default=None,
        help="Path to a JSON selector profile. Overrides --profile when provided.",
    )
    parser.add_argument("--headed", action="store_true")
    parser.add_argument(
        "--browser-channel",
        default=None,
        help="Optional installed browser channel, for example msedge or chrome.",
    )
    parser.add_argument("--user-data-dir", default=None, help="Optional persistent browser profile directory.")
    parser.add_argument("--wait-before-run", type=float, default=0.0, help="Seconds to wait before reading the page.")
    parser.add_argument(
        "--allow-real-send",
        action="store_true",
        help="Allow filling the reply input and clicking send. Without this flag, dry-run mode is enforced.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Read and decide, but do not fill or send replies.")
    parser.add_argument(
        "--process-all-visible",
        action="store_true",
        help="Process all visible buyer messages. By default only the latest visible buyer message is processed.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Keep running in a polling loop after processing initial messages.",
    )
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds (used with --watch).")
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Stop after this many polling cycles. Useful for tests and demos.",
    )
    args = parser.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Python Playwright is not installed. Run: pip install playwright && python -m playwright install chromium"
        ) from exc

    profile = (
        load_profile_from_json(args.selector_profile_json)
        if args.selector_profile_json
        else get_builtin_profile(args.profile)
    )
    page_url = args.page_url or profile.default_url
    if not page_url:
        raise SystemExit("No page URL was provided. Use --page-url or set default_url in the selector profile.")

    runtime = LocalAgentRuntime(agent_id=args.agent_id, merchant_id=args.merchant_id)
    client = LocalBackendClient(base_url=args.backend_url)

    with sync_playwright() as playwright:
        launch_options = {"headless": not args.headed}
        if args.browser_channel:
            launch_options["channel"] = args.browser_channel
        if args.user_data_dir:
            context = playwright.chromium.launch_persistent_context(args.user_data_dir, **launch_options)
            page = context.pages[0] if context.pages else context.new_page()
            closer = context
        else:
            browser = playwright.chromium.launch(**launch_options)
            page = browser.new_page()
            closer = browser
        page.goto(page_url)
        if args.wait_before_run > 0:
            time.sleep(args.wait_before_run)
        effective_dry_run = args.dry_run or not args.allow_real_send
        adapter = build_browser_web_chat_adapter(
            page=page,
            platform=profile.platform,
            selectors=profile.selectors,
            agent_id=args.agent_id,
            default_conversation_id=profile.default_conversation_id,
            dry_run=effective_dry_run,
            latest_only=not args.process_all_visible,
            selector_profile_name=profile.name,
        )
        if args.watch:
            loop = LocalAgentLoop(
                runtime=runtime,
                adapter=adapter,
                backend_client=client,
                poll_interval_seconds=args.interval,
            )
            summary = loop.run(max_cycles=args.max_cycles)
        else:
            summary = runtime.process_once(adapter, client)
        if hasattr(summary, "__dict__"):
            summary = summary.__dict__
        summary["safety"] = {
            "allow_real_send": args.allow_real_send,
            "dry_run": effective_dry_run,
            "latest_only": not args.process_all_visible,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        closer.close()


if __name__ == "__main__":
    main()
