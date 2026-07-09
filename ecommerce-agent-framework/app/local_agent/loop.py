"""Polling loop for long-running Local Agent processes."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.local_agent.adapters.base import BasePlatformAdapter
from app.local_agent.runtime import LocalAgentRuntime


@dataclass
class LocalAgentLoopSummary:
    agent_id: str
    merchant_id: str
    platform: str
    cycles: int = 0
    processed_count: int = 0
    errors: List[str] = field(default_factory=list)
    cycle_summaries: List[Dict[str, Any]] = field(default_factory=list)


class LocalAgentLoop:
    def __init__(
        self,
        runtime: LocalAgentRuntime,
        adapter: BasePlatformAdapter,
        backend_client: Any,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        self.runtime = runtime
        self.adapter = adapter
        self.backend_client = backend_client
        self.poll_interval_seconds = poll_interval_seconds
        self._stop_requested = False

    def stop(self) -> None:
        self._stop_requested = True

    def run(self, max_cycles: Optional[int] = None) -> LocalAgentLoopSummary:
        summary = LocalAgentLoopSummary(
            agent_id=self.runtime.agent_id,
            merchant_id=self.runtime.merchant_id,
            platform=getattr(self.adapter, "platform", "unknown"),
        )

        while not self._stop_requested:
            if max_cycles is not None and summary.cycles >= max_cycles:
                break

            try:
                cycle_summary = self.runtime.process_once(self.adapter, self.backend_client)
                summary.cycle_summaries.append(cycle_summary)
                summary.processed_count += int(cycle_summary.get("processed_count", 0))
            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as exc:  # pragma: no cover - defensive runtime guard.
                summary.errors.append(str(exc))

            summary.cycles += 1
            if max_cycles is not None and summary.cycles >= max_cycles:
                break
            if self.poll_interval_seconds > 0:
                time.sleep(self.poll_interval_seconds)

        return summary
