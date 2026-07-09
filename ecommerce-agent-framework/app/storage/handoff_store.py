"""Persistent handoff ticket store for local AI customer-service agents.

Each ticket represents a conversation that was flagged for human review.
The store uses a local JSON file for persistence (MVP; can be migrated to
Redis/PostgreSQL later).
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from copy import deepcopy
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional


HANDOFF_STATUS_PENDING = "pending"
HANDOFF_STATUS_PROCESSING = "processing"
HANDOFF_STATUS_RESOLVED = "resolved"
HANDOFF_STATUS_RETURNED_TO_AI = "returned_to_ai"
HANDOFF_STATUS_CLOSED = "closed"

VALID_STATUSES = {
    HANDOFF_STATUS_PENDING,
    HANDOFF_STATUS_PROCESSING,
    HANDOFF_STATUS_RESOLVED,
    HANDOFF_STATUS_RETURNED_TO_AI,
    HANDOFF_STATUS_CLOSED,
}

ACTIVE_STATUSES = {HANDOFF_STATUS_PENDING, HANDOFF_STATUS_PROCESSING}


def _content_hash(merchant_id: str, platform: str, external_conversation_id: str,
                  external_message_id: Optional[str], customer_message: str) -> str:
    """Generate a stable dedup key for a handoff ticket."""
    raw = f"{merchant_id}|{platform}|{external_conversation_id}|{external_message_id or ''}|{customer_message}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _now_iso() -> str:
    return datetime.now().isoformat()


class HandoffStore:
    def __init__(self, file_path: Optional[str] = None) -> None:
        self.file_path = file_path or os.path.join(os.getcwd(), "data", "handoff_tickets.json")
        self._lock = Lock()
        # ticket_id -> ticket dict
        self._tickets: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_ticket(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new handoff ticket, or return the existing one if a
        duplicate (same merchant + platform + external_conversation_id +
        external_message_id) already exists."""
        merchant_id = payload.get("merchant_id") or "default"
        platform = payload.get("platform") or "unknown"
        external_conversation_id = payload.get("external_conversation_id") or ""
        external_message_id = payload.get("external_message_id")
        customer_message = payload.get("customer_message") or ""
        content_id = payload.get("content_id") or _content_hash(
            merchant_id, platform, external_conversation_id,
            external_message_id, customer_message,
        )

        with self._lock:
            existing = self._find_duplicate_locked(merchant_id, platform,
                                                     external_conversation_id,
                                                     external_message_id, content_id)
            if existing is not None:
                # Update the existing ticket's fields instead of creating a duplicate
                now = _now_iso()
                for key in ("customer_message", "recommended_reply", "reason",
                            "blockers", "risk_level", "confidence"):
                    if key in payload:
                        if key == "recommended_reply" and not payload.get(key):
                            continue
                        existing[key] = payload[key]
                existing["updated_at"] = now
                existing["duplicate_count"] = existing.get("duplicate_count", 1) + 1
                if existing.get("status") in (HANDOFF_STATUS_CLOSED, HANDOFF_STATUS_RESOLVED):
                    existing["status"] = HANDOFF_STATUS_PENDING
                    existing["resolved_at"] = None
                    existing["human_reply"] = None
                self._save_locked()
                return deepcopy(existing)

            now = _now_iso()
            ticket_id = str(uuid.uuid4())
            ticket: Dict[str, Any] = {
                "ticket_id": ticket_id,
                "merchant_id": merchant_id,
                "platform": platform,
                "conversation_id": payload.get("conversation_id", ""),
                "external_conversation_id": external_conversation_id,
                "external_message_id": external_message_id or "",
                "content_id": content_id,
                "customer_message": customer_message,
                "recommended_reply": payload.get("recommended_reply", ""),
                "reason": payload.get("reason", ""),
                "blockers": list(payload.get("blockers") or []),
                "risk_level": payload.get("risk_level", ""),
                "confidence": payload.get("confidence"),
                "status": HANDOFF_STATUS_PENDING,
                "assigned_to": None,
                "human_reply": None,
                "created_at": now,
                "updated_at": now,
                "resolved_at": None,
                "returned_to_ai_at": None,
                "duplicate_count": 0,
                "source": payload.get("source", "rpa_decision"),
            }
            self._tickets[ticket_id] = ticket
            self._save_locked()
            return deepcopy(ticket)

    def get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            return deepcopy(ticket) if ticket else None

    def list_tickets(
        self,
        merchant_id: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            items = list(self._tickets.values())

        if merchant_id:
            items = [t for t in items if t.get("merchant_id") == merchant_id]
        if platform:
            items = [t for t in items if t.get("platform") == platform]
        if status:
            items = [t for t in items if t.get("status") == status]

        items.sort(key=lambda t: t.get("updated_at") or t.get("created_at") or "", reverse=True)
        return items[:limit]

    def update_status(self, ticket_id: str, new_status: str,
                      **extra: Any) -> Optional[Dict[str, Any]]:
        if new_status not in VALID_STATUSES:
            return None

        now = _now_iso()
        with self._lock:
            ticket = self._tickets.get(ticket_id)
            if ticket is None:
                return None

            ticket["status"] = new_status
            ticket["updated_at"] = now

            if new_status == HANDOFF_STATUS_RESOLVED:
                ticket["resolved_at"] = now
                if "human_reply" in extra:
                    ticket["human_reply"] = extra["human_reply"]
            elif new_status == HANDOFF_STATUS_RETURNED_TO_AI:
                ticket["returned_to_ai_at"] = now
            elif new_status == HANDOFF_STATUS_PROCESSING:
                if "assigned_to" in extra:
                    ticket["assigned_to"] = extra["assigned_to"]

            self._save_locked()
            return deepcopy(ticket)

    def get_summary(self, merchant_id: Optional[str] = None) -> Dict[str, Any]:
        """Return pending/processing counts grouped by platform."""
        with self._lock:
            items = list(self._tickets.values())

        if merchant_id:
            items = [t for t in items if t.get("merchant_id") == merchant_id]

        platforms: Dict[str, Dict[str, int]] = {}
        total_pending = 0
        total_processing = 0

        for ticket in items:
            status = ticket.get("status", "")
            if status not in ACTIVE_STATUSES:
                continue
            plat = ticket.get("platform") or "unknown"
            if plat not in platforms:
                platforms[plat] = {"pending": 0, "processing": 0}
            if status == HANDOFF_STATUS_PENDING:
                platforms[plat]["pending"] += 1
                total_pending += 1
            elif status == HANDOFF_STATUS_PROCESSING:
                platforms[plat]["processing"] += 1
                total_processing += 1

        return {
            "platforms": platforms,
            "total_pending": total_pending,
            "total_processing": total_processing,
            "total_active": total_pending + total_processing,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_duplicate_locked(
        self,
        merchant_id: str,
        platform: str,
        external_conversation_id: str,
        external_message_id: Optional[str],
        content_id: str,
    ) -> Optional[Dict[str, Any]]:
        for ticket in self._tickets.values():
            if ticket.get("merchant_id") != merchant_id:
                continue
            if ticket.get("platform") != platform:
                continue
            if ticket.get("external_conversation_id") != external_conversation_id:
                continue
            # Match by external_message_id if present, else by content_id
            if external_message_id and ticket.get("external_message_id") == external_message_id:
                return ticket
            if not external_message_id and ticket.get("content_id") == content_id:
                return ticket
        return None

    def _load(self) -> None:
        if not os.path.exists(self.file_path):
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                self._tickets = {
                    str(k): v for k, v in data.items()
                    if isinstance(v, dict) and v.get("ticket_id")
                }
        except Exception:
            self._tickets = {}

    def _save_locked(self) -> None:
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        tmp_path = f"{self.file_path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(self._tickets, handle, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.file_path)


handoff_store = HandoffStore()
