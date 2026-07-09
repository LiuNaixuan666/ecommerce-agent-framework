"""Local Agent runtime orchestration.

This module defines the execution flow used by platform adapters. The first
Mock UI can exercise the same protocol from the frontend, while later
Playwright-based adapters can call this runtime directly.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.local_agent.adapters.base import BasePlatformAdapter, PlatformMessage, SendResult


class LocalAgentRuntime:
    def __init__(
        self,
        agent_id: str = "local-agent-001",
        merchant_id: str = "default",
        max_message_age_seconds: int = 300,
        send_retry_attempts: int = 2,
    ) -> None:
        self.agent_id = agent_id
        self.merchant_id = merchant_id
        self.max_message_age_seconds = max_message_age_seconds
        self.send_retry_attempts = max(1, send_retry_attempts)
        # Track the latest buyer message seen for heartbeat reporting
        self._last_buyer_message: Optional[str] = None
        self._last_decision_snapshot: Optional[Dict[str, Any]] = None

    def build_rpa_message_payload(self, message: PlatformMessage) -> Dict[str, Any]:
        return {
            "merchant_id": self.merchant_id,
            "platform": message.platform,
            "external_conversation_id": message.external_conversation_id,
            "external_message_id": message.external_message_id,
            "customer_message": message.customer_message,
            "customer_id": message.customer_id,
            "customer_name": message.customer_name,
            "page_context": message.page_context,
            "metadata": {
                **message.metadata,
                "agent_id": self.agent_id,
                "agent_type": "self_built_local_agent",
            },
        }

    def build_send_result_payload(
        self,
        message: PlatformMessage,
        decision_response: Dict[str, Any],
        execution: SendResult,
    ) -> Dict[str, Any]:
        request_id = decision_response.get("request_id") or execution.request_id
        return self._json_ready(
            {
                **asdict(execution),
                "request_id": request_id,
                "merchant_id": self.merchant_id,
                "platform": message.platform,
                "external_conversation_id": message.external_conversation_id,
                "external_message_id": message.external_message_id,
                "customer_message": message.customer_message,
                "agent_id": self.agent_id,
            }
        )

    def decide_execution_text(self, decision_response: Dict[str, Any]) -> Optional[str]:
        instruction = decision_response.get("rpa_instruction") or {}
        decision = decision_response.get("decision") or {}
        if not decision.get("auto_send_allowed"):
            return None
        return instruction.get("send_text")

    def process_once(self, adapter: BasePlatformAdapter, backend_client: Any) -> Dict[str, Any]:
        health = adapter.health_check()
        backend_client.post_heartbeat(self._build_heartbeat_payload(adapter, health))

        processed: List[Dict[str, Any]] = []
        latest_decision: Optional[Dict[str, Any]] = None
        for message in adapter.read_new_messages():
            self._last_buyer_message = message.customer_message
            if self._is_message_stale(message):
                execution = self._build_skipped_stale_result(message)
                result_payload = self.build_send_result_payload(message, {}, execution)
                send_result_response = backend_client.post_send_result(result_payload)
                processed.append(
                    {
                        "message_id": message.external_message_id,
                        "conversation_id": message.external_conversation_id,
                        "action": "skipped_stale",
                        "decision": {},
                        "execution": result_payload,
                        "send_result": send_result_response,
                    }
                )
                continue

            decision_response = backend_client.post_rpa_message(self.build_rpa_message_payload(message))
            send_text = self.decide_execution_text(decision_response)
            if send_text:
                execution = self._send_with_retry(adapter, message, send_text)
            else:
                execution = adapter.mark_handoff(message, self._handoff_reason(decision_response))

            result_payload = self.build_send_result_payload(message, decision_response, execution)
            send_result_response = backend_client.post_send_result(result_payload)
            processed.append(
                {
                    "message_id": message.external_message_id,
                    "conversation_id": message.external_conversation_id,
                    "action": "send" if send_text else "handoff",
                    "decision": decision_response,
                    "execution": result_payload,
                    "send_result": send_result_response,
                }
            )
            # Keep the last decision snapshot for heartbeat update
            decision = decision_response.get("decision", {})
            reply = decision_response.get("reply", {})
            trace = decision_response.get("trace", {})
            page_ctx = message.page_context or {}
            latest_decision = {
                "latest_buyer_message": message.customer_message,
                "recommended_reply": (
                    reply.get("recommended_reply")
                    or decision.get("recommended_reply")
                    or decision_response.get("recommended_reply")
                ),
                "auto_send_allowed": decision.get("auto_send_allowed", False),
                "auto_send_blockers": decision.get("auto_send_blockers", decision.get("risk_reasons", [])),
                "risk_level": decision.get("risk_level", "low"),
                "handoff_required": decision.get("requires_human_review", False),
                "handoff_reason": decision.get("handoff_reason"),
                "intent": trace.get("intent") or decision.get("intent"),
                "retrieval_type": trace.get("retrieval_type"),
                "sources": trace.get("sources", []),
                "evidence_sources": trace.get("evidence_sources", []),
                "confidence": decision.get("confidence"),
                "conversation_id": message.external_conversation_id,
                # Pull product context from page_context for UI display
                "product_name": page_ctx.get("product_name") or page_ctx.get("title"),
                "sku": page_ctx.get("sku"),
                "product_price": str(page_ctx.get("price", "")) if page_ctx.get("price") is not None else None,
                "stock": page_ctx.get("stock") or page_ctx.get("inventory"),
                "send_status": execution.send_status,
            }
            self._last_decision_snapshot = latest_decision

        # Update heartbeat with the latest decision snapshot (if any message was processed)
        if latest_decision:
            backend_client.post_heartbeat(self._build_heartbeat_payload(adapter, health))

        return {
            "agent_id": self.agent_id,
            "merchant_id": self.merchant_id,
            "platform": getattr(adapter, "platform", "unknown"),
            "processed_count": len(processed),
            "processed": processed,
        }

    def _build_heartbeat_payload(self, adapter: BasePlatformAdapter, health: Dict[str, Any]) -> Dict[str, Any]:
        metadata = {
            **health,
            **(self._last_decision_snapshot or {}),
        }
        return {
            "agent_id": self.agent_id,
            "platform": getattr(adapter, "platform", health.get("platform", "unknown")),
            "merchant_id": self.merchant_id,
            "status": self._heartbeat_status(health.get("status")),
            "watched_window_title": health.get("watched_window_title"),
            "current_conversation_id": health.get("current_conversation_id"),
            "last_message_id": health.get("last_message_id"),
            "last_error": health.get("last_error"),
            "latest_buyer_message": self._last_buyer_message,
            "selector_profile": getattr(adapter, "selector_profile_name", None),
            "current_page_url": health.get("current_page_url"),
            "metadata": metadata,
        }

    def _heartbeat_status(self, status: Any) -> str:
        if status in {"running", "paused", "stopped", "error"}:
            return str(status)
        if status in {"not_detected", "not_logged_in"}:
            return "error"
        return "running"

    def _handoff_reason(self, decision_response: Dict[str, Any]) -> str:
        instruction = decision_response.get("rpa_instruction") or {}
        decision = decision_response.get("decision") or {}
        return (
            instruction.get("handoff_note")
            or decision.get("handoff_reason")
            or "Backend decision did not allow auto send."
        )

    def _is_message_stale(self, message: PlatformMessage) -> bool:
        age_seconds = (datetime.now() - message.observed_at).total_seconds()
        return age_seconds > self.max_message_age_seconds

    def _build_skipped_stale_result(self, message: PlatformMessage) -> SendResult:
        age_seconds = int((datetime.now() - message.observed_at).total_seconds())
        return SendResult(
            request_id=f"local-stale-{message.external_message_id}",
            merchant_id=self.merchant_id,
            platform=message.platform,
            external_conversation_id=message.external_conversation_id,
            external_message_id=message.external_message_id,
            send_status="skipped_stale",
            agent_id=self.agent_id,
            error_code="MESSAGE_STALE",
            error_message=f"Message age {age_seconds}s exceeded limit {self.max_message_age_seconds}s.",
            metadata={
                "message_observed_at": message.observed_at.isoformat(),
                "max_message_age_seconds": self.max_message_age_seconds,
                "age_seconds": age_seconds,
            },
        )

    def _send_with_retry(
        self,
        adapter: BasePlatformAdapter,
        message: PlatformMessage,
        send_text: str,
    ) -> SendResult:
        last_result: Optional[SendResult] = None
        last_error: Optional[Exception] = None

        for attempt in range(1, self.send_retry_attempts + 1):
            try:
                result = adapter.send_text(message, send_text)
                result.metadata = {
                    **result.metadata,
                    "send_attempts": attempt,
                    "max_send_attempts": self.send_retry_attempts,
                }
                last_result = result
                if result.send_status in {"success", "skipped_dry_run"}:
                    return result
            except Exception as exc:  # pragma: no cover - covered through behavior tests.
                last_error = exc

        if last_result is not None:
            return SendResult(
                request_id=last_result.request_id,
                merchant_id=self.merchant_id,
                platform=message.platform,
                external_conversation_id=message.external_conversation_id,
                external_message_id=message.external_message_id,
                send_status="failed",
                sent_text=last_result.sent_text,
                agent_id=self.agent_id,
                error_code=last_result.error_code or "SEND_FAILED",
                error_message=last_result.error_message or "Send did not succeed after retries.",
                metadata={
                    **last_result.metadata,
                    "send_attempts": self.send_retry_attempts,
                    "max_send_attempts": self.send_retry_attempts,
                },
            )

        return SendResult(
            request_id=f"local-send-failed-{message.external_message_id}",
            merchant_id=self.merchant_id,
            platform=message.platform,
            external_conversation_id=message.external_conversation_id,
            external_message_id=message.external_message_id,
            send_status="failed",
            sent_text=send_text,
            agent_id=self.agent_id,
            error_code="SEND_EXCEPTION",
            error_message=str(last_error) if last_error else "Unknown send failure.",
            metadata={
                "send_attempts": self.send_retry_attempts,
                "max_send_attempts": self.send_retry_attempts,
            },
        )

    def _json_ready(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {key: self._json_ready(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._json_ready(item) for item in value]
        return value
