from datetime import datetime, timedelta

from app.local_agent.adapters.base import SendResult
from app.local_agent.adapters.mock_shop import MockShopAdapter
from app.local_agent.loop import LocalAgentLoop
from app.local_agent.runtime import LocalAgentRuntime


class FakeBackendClient:
    def __init__(self, decision_response):
        self.decision_response = decision_response
        self.heartbeats = []
        self.rpa_messages = []
        self.send_results = []

    def post_heartbeat(self, payload):
        self.heartbeats.append(payload)
        return {"ok": True}

    def post_rpa_message(self, payload):
        self.rpa_messages.append(payload)
        return self.decision_response

    def post_send_result(self, payload):
        self.send_results.append(payload)
        mapping = {
            "success": "auto_sent",
            "failed": "send_failed",
            "handoff": "handoff_required",
            "skipped_stale": "skipped_stale",
            "skipped_dry_run": "skipped_dry_run",
        }
        return {"processing_status": mapping[payload["send_status"]]}


class FlakySendAdapter(MockShopAdapter):
    def __init__(self, failures_before_success=1, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.failures_before_success = failures_before_success
        self.send_attempts = 0

    def send_text(self, message, text):
        self.send_attempts += 1
        if self.send_attempts <= self.failures_before_success:
            raise RuntimeError("temporary send failure")
        return super().send_text(message, text)


class FailedResultAdapter(MockShopAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.send_attempts = 0

    def send_text(self, message, text):
        self.send_attempts += 1
        return SendResult(
            request_id="pending",
            merchant_id="default",
            platform=self.platform,
            external_conversation_id=message.external_conversation_id,
            external_message_id=message.external_message_id,
            send_status="failed",
            sent_text=text,
            agent_id=self.agent_id,
            error_code="UI_SEND_FAILED",
            error_message="Fake UI did not accept the message.",
        )


class DryRunAdapter(MockShopAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.send_attempts = 0

    def send_text(self, message, text):
        self.send_attempts += 1
        return SendResult(
            request_id="pending",
            merchant_id="default",
            platform=self.platform,
            external_conversation_id=message.external_conversation_id,
            external_message_id=message.external_message_id,
            send_status="skipped_dry_run",
            sent_text=text,
            agent_id=self.agent_id,
            error_code="DRY_RUN",
            error_message="Dry run mode.",
            metadata={"dry_run": True},
        )


class NotDetectedAdapter(MockShopAdapter):
    def health_check(self):
        return {
            "status": "not_detected",
            "platform": self.platform,
            "watched_window_title": "Missing Chat Page",
            "last_error": "root selector not found",
        }


def low_risk_send_decision():
    return {
        "request_id": "backend-request-send",
        "recommended_reply": "This item is currently in stock.",
        "decision": {
            "action": "send",
            "auto_send_allowed": True,
            "risk_level": "low",
            "confidence": 0.8,
            "auto_send_blockers": [],
        },
        "rpa_instruction": {
            "operation": "send_message",
            "send_text": "This item is currently in stock.",
            "handoff_note": None,
        },
    }


def medium_risk_handoff_decision():
    return {
        "request_id": "backend-request-handoff",
        "recommended_reply": "Please hand this conversation to a human agent.",
        "decision": {
            "action": "handoff",
            "auto_send_allowed": False,
            "risk_level": "medium",
            "confidence": 0.6,
            "auto_send_blockers": ["risk_medium"],
            "handoff_reason": "Return policy requires human confirmation.",
        },
        "rpa_instruction": {
            "operation": "handoff",
            "send_text": None,
            "handoff_note": "Return policy requires human confirmation.",
        },
    }


def test_mock_shop_adapter_reads_new_messages_once():
    adapter = MockShopAdapter()
    adapter.add_buyer_message("Is this item in stock?")

    first_batch = adapter.read_new_messages()
    second_batch = adapter.read_new_messages()

    assert len(first_batch) == 1
    assert first_batch[0].customer_message == "Is this item in stock?"
    assert second_batch == []


def test_local_agent_runtime_builds_rpa_payload():
    adapter = MockShopAdapter()
    message = adapter.add_buyer_message("Is this item in stock?")
    runtime = LocalAgentRuntime(agent_id="agent-test", merchant_id="merchant-test")

    payload = runtime.build_rpa_message_payload(message)

    assert payload["merchant_id"] == "merchant-test"
    assert payload["platform"] == "mock_shop"
    assert payload["external_conversation_id"] == message.external_conversation_id
    assert payload["external_message_id"] == message.external_message_id
    assert payload["customer_message"] == "Is this item in stock?"
    assert payload["metadata"]["agent_id"] == "agent-test"
    assert payload["page_context"]["product_name"] == "Mock Book Set"


def test_runtime_builds_send_result_payload_with_backend_request_id():
    adapter = MockShopAdapter(agent_id="agent-test")
    message = adapter.add_buyer_message("Is this item in stock?")
    execution = adapter.send_text(message, "This item is currently in stock.")
    runtime = LocalAgentRuntime(agent_id="agent-test", merchant_id="merchant-test")

    payload = runtime.build_send_result_payload(
        message,
        decision_response={"request_id": "backend-request-001"},
        execution=execution,
    )

    assert payload["request_id"] == "backend-request-001"
    assert payload["merchant_id"] == "merchant-test"
    assert payload["send_status"] == "success"
    assert payload["sent_text"] == "This item is currently in stock."


def test_process_once_auto_sends_low_risk_message():
    adapter = MockShopAdapter(agent_id="agent-test")
    adapter.add_buyer_message("Is this item in stock?")
    runtime = LocalAgentRuntime(agent_id="agent-test", merchant_id="merchant-test")
    backend = FakeBackendClient(low_risk_send_decision())

    summary = runtime.process_once(adapter, backend)

    assert summary["processed_count"] == 1
    assert summary["processed"][0]["action"] == "send"
    assert len(backend.heartbeats) == 2
    assert backend.heartbeats[0]["metadata"].get("recommended_reply") is None
    decision_heartbeat = backend.heartbeats[1]
    assert decision_heartbeat["latest_buyer_message"] == "Is this item in stock?"
    assert (
        decision_heartbeat["metadata"]["recommended_reply"]
        == "This item is currently in stock."
    )
    assert decision_heartbeat["metadata"]["auto_send_allowed"] is True
    assert decision_heartbeat["metadata"]["send_status"] == "success"
    assert len(backend.rpa_messages) == 1
    assert len(backend.send_results) == 1
    assert len(adapter.sent_messages) == 1
    assert adapter.sent_messages[0]["text"] == "This item is currently in stock."
    assert backend.send_results[0]["request_id"] == "backend-request-send"
    assert backend.send_results[0]["send_status"] == "success"


def test_process_once_maps_not_detected_heartbeat_status_to_error():
    adapter = NotDetectedAdapter(agent_id="agent-test")
    runtime = LocalAgentRuntime(agent_id="agent-test", merchant_id="merchant-test")
    backend = FakeBackendClient(low_risk_send_decision())

    summary = runtime.process_once(adapter, backend)

    assert summary["processed_count"] == 0
    assert backend.heartbeats[0]["status"] == "error"
    assert backend.heartbeats[0]["metadata"]["status"] == "not_detected"


def test_process_once_handoffs_when_auto_send_blocked():
    adapter = MockShopAdapter(agent_id="agent-test")
    adapter.add_buyer_message("Can I return this item after opening it?")
    runtime = LocalAgentRuntime(agent_id="agent-test", merchant_id="merchant-test")
    backend = FakeBackendClient(medium_risk_handoff_decision())

    summary = runtime.process_once(adapter, backend)

    assert summary["processed_count"] == 1
    assert summary["processed"][0]["action"] == "handoff"
    assert len(adapter.sent_messages) == 0
    assert len(adapter.handoffs) == 1
    assert backend.send_results[0]["request_id"] == "backend-request-handoff"
    assert backend.send_results[0]["send_status"] == "handoff"
    assert backend.send_results[0]["error_message"] == "Return policy requires human confirmation."


def test_process_once_skips_stale_message_before_backend_decision():
    adapter = MockShopAdapter(agent_id="agent-test")
    adapter.add_buyer_message(
        "Is this item in stock?",
        observed_at=datetime.now() - timedelta(seconds=20),
    )
    runtime = LocalAgentRuntime(
        agent_id="agent-test",
        merchant_id="merchant-test",
        max_message_age_seconds=5,
    )
    backend = FakeBackendClient(low_risk_send_decision())

    summary = runtime.process_once(adapter, backend)

    assert summary["processed_count"] == 1
    assert summary["processed"][0]["action"] == "skipped_stale"
    assert len(backend.rpa_messages) == 0
    assert len(backend.send_results) == 1
    assert backend.send_results[0]["send_status"] == "skipped_stale"
    assert backend.send_results[0]["error_code"] == "MESSAGE_STALE"
    assert backend.send_results[0]["metadata"]["max_message_age_seconds"] == 5


def test_process_once_retries_send_after_exception():
    adapter = FlakySendAdapter(agent_id="agent-test", failures_before_success=1)
    adapter.add_buyer_message("Is this item in stock?")
    runtime = LocalAgentRuntime(
        agent_id="agent-test",
        merchant_id="merchant-test",
        send_retry_attempts=2,
    )
    backend = FakeBackendClient(low_risk_send_decision())

    summary = runtime.process_once(adapter, backend)

    assert summary["processed_count"] == 1
    assert summary["processed"][0]["action"] == "send"
    assert adapter.send_attempts == 2
    assert backend.send_results[0]["send_status"] == "success"
    assert backend.send_results[0]["metadata"]["send_attempts"] == 2


def test_process_once_reports_failed_after_send_retries_exhausted():
    adapter = FailedResultAdapter(agent_id="agent-test")
    adapter.add_buyer_message("Is this item in stock?")
    runtime = LocalAgentRuntime(
        agent_id="agent-test",
        merchant_id="merchant-test",
        send_retry_attempts=2,
    )
    backend = FakeBackendClient(low_risk_send_decision())

    summary = runtime.process_once(adapter, backend)

    assert summary["processed_count"] == 1
    assert summary["processed"][0]["action"] == "send"
    assert adapter.send_attempts == 2
    assert backend.send_results[0]["send_status"] == "failed"
    assert backend.send_results[0]["error_code"] == "UI_SEND_FAILED"
    assert backend.send_results[0]["metadata"]["send_attempts"] == 2


def test_process_once_does_not_retry_dry_run_result():
    adapter = DryRunAdapter(agent_id="agent-test")
    adapter.add_buyer_message("Is this item in stock?")
    runtime = LocalAgentRuntime(
        agent_id="agent-test",
        merchant_id="merchant-test",
        send_retry_attempts=2,
    )
    backend = FakeBackendClient(low_risk_send_decision())

    summary = runtime.process_once(adapter, backend)

    assert summary["processed_count"] == 1
    assert adapter.send_attempts == 1
    assert backend.send_results[0]["send_status"] == "skipped_dry_run"
    assert backend.send_results[0]["metadata"]["dry_run"] is True


def test_local_agent_loop_polls_multiple_cycles_and_keeps_heartbeats():
    adapter = MockShopAdapter(agent_id="agent-test")
    adapter.add_buyer_message("Is this item in stock?")
    runtime = LocalAgentRuntime(agent_id="agent-test", merchant_id="merchant-test")
    backend = FakeBackendClient(low_risk_send_decision())
    loop = LocalAgentLoop(
        runtime=runtime,
        adapter=adapter,
        backend_client=backend,
        poll_interval_seconds=0,
    )

    summary = loop.run(max_cycles=3)

    assert summary.cycles == 3
    assert summary.processed_count == 1
    assert len(summary.cycle_summaries) == 3
    # Each poll emits a health heartbeat; the processed message adds one
    # decision heartbeat so the UI can retain reply and risk details.
    assert len(backend.heartbeats) == 4
    assert backend.heartbeats[1]["metadata"]["recommended_reply"] == (
        "This item is currently in stock."
    )
    assert all(
        heartbeat["metadata"].get("recommended_reply")
        == "This item is currently in stock."
        for heartbeat in backend.heartbeats[1:]
    )
    assert len(backend.rpa_messages) == 1
    assert len(backend.send_results) == 1


def test_local_agent_loop_records_cycle_errors():
    class BrokenRuntime(LocalAgentRuntime):
        def process_once(self, adapter, backend_client):
            raise RuntimeError("boom")

    adapter = MockShopAdapter(agent_id="agent-test")
    backend = FakeBackendClient(low_risk_send_decision())
    loop = LocalAgentLoop(
        runtime=BrokenRuntime(agent_id="agent-test", merchant_id="merchant-test"),
        adapter=adapter,
        backend_client=backend,
        poll_interval_seconds=0,
    )

    summary = loop.run(max_cycles=2)

    assert summary.cycles == 2
    assert summary.processed_count == 0
    assert summary.errors == ["boom", "boom"]
