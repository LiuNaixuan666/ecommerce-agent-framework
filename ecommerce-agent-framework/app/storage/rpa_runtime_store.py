"""Runtime store for Local Agent status and RPA send results.

The first Local Agent iteration only needs process-local state so the backend
can expose a stable protocol before we add durable tables.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


class RpaRuntimeStore:
    def __init__(self, max_send_results: int = 500) -> None:
        self.max_send_results = max_send_results
        self.send_results: List[Dict[str, Any]] = []
        self.agent_heartbeats: Dict[str, Dict[str, Any]] = {}

    def save_send_result(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        record = {
            "id": f"send-result-{len(self.send_results) + 1}",
            "created_at": now,
            **payload,
            "updated_at": now,
        }
        self.send_results.append(record)
        if len(self.send_results) > self.max_send_results:
            self.send_results = self.send_results[-self.max_send_results :]
        return record

    def list_send_results(
        self,
        merchant_id: Optional[str] = None,
        platform: Optional[str] = None,
        external_conversation_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        results = self.send_results
        if merchant_id:
            results = [item for item in results if item.get("merchant_id") == merchant_id]
        if platform:
            results = [item for item in results if item.get("platform") == platform]
        if external_conversation_id:
            results = [
                item
                for item in results
                if item.get("external_conversation_id") == external_conversation_id
            ]
        return results[-limit:]

    def save_heartbeat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        now = datetime.now().isoformat()
        agent_id = payload["agent_id"]
        record = {
            **payload,
            "last_heartbeat_at": now,
            "updated_at": now,
        }
        self.agent_heartbeats[agent_id] = record
        return record

    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        return self.agent_heartbeats.get(agent_id)

    def list_agent_status(
        self,
        merchant_id: Optional[str] = None,
        platform: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        statuses = list(self.agent_heartbeats.values())
        if merchant_id:
            statuses = [item for item in statuses if item.get("merchant_id") == merchant_id]
        if platform:
            statuses = [item for item in statuses if item.get("platform") == platform]
        return statuses


rpa_runtime_store = RpaRuntimeStore()
