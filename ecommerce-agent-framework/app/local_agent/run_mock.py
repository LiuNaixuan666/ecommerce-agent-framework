"""Run MockShop Local Agent processing cycles.

Example:
    python -m app.local_agent.run_mock --message "Is this in stock?"
    python -m app.local_agent.run_mock --watch --interval 2
"""

from __future__ import annotations

import argparse
import json

from app.local_agent.adapters.mock_shop import MockShopAdapter
from app.local_agent.http_client import LocalBackendClient
from app.local_agent.loop import LocalAgentLoop
from app.local_agent.runtime import LocalAgentRuntime


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MockShop Local Agent cycles.")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000")
    parser.add_argument("--agent-id", default="local-agent-mock")
    parser.add_argument("--merchant-id", default="mock_merchant")
    parser.add_argument("--message", action="append", default=None)
    parser.add_argument("--conversation-id", default="mock-conversation-cli")
    parser.add_argument("--watch", action="store_true", help="Keep polling after initial messages are processed.")
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds.")
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=None,
        help="Stop after this many polling cycles. Useful for tests and demos.",
    )
    args = parser.parse_args()

    adapter = MockShopAdapter(agent_id=args.agent_id)
    messages = args.message or ["Is this item in stock?"]
    for index, message in enumerate(messages, start=1):
        conversation_id = args.conversation_id
        if len(messages) > 1:
            conversation_id = f"{args.conversation_id}-{index}"
        adapter.add_buyer_message(message, external_conversation_id=conversation_id)

    runtime = LocalAgentRuntime(agent_id=args.agent_id, merchant_id=args.merchant_id)
    client = LocalBackendClient(base_url=args.backend_url)
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
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
