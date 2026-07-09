from app.local_agent.adapters.base import SendResult
from app.local_agent.adapters.generic_web_chat import GenericWebChatAdapter
from app.local_agent.watchers.base import RawMessageEvent


class FakeWatcher:
    def __init__(self, events):
        self.events = events

    def detect_app(self):
        return True

    def detect_login_status(self):
        return True

    def read_events(self):
        return list(self.events)

    def health_check(self):
        return {
            "status": "running",
            "watched_window_title": "Fake Web Chat",
        }


class FakeContextExtractor:
    def extract_for_message(self, event):
        return {
            "product_name": "Adapter Test Product",
            "event_id": event.external_message_id,
        }


class FakeExecutor:
    def __init__(self):
        self.sent = []
        self.handoffs = []

    def send_text(self, message, text):
        self.sent.append((message.external_message_id, text))
        return SendResult(
            request_id="pending",
            merchant_id="default",
            platform=message.platform,
            external_conversation_id=message.external_conversation_id,
            external_message_id=message.external_message_id,
            send_status="success",
            sent_text=text,
            agent_id="fake-agent",
        )

    def mark_handoff(self, message, reason):
        self.handoffs.append((message.external_message_id, reason))
        return SendResult(
            request_id="pending",
            merchant_id="default",
            platform=message.platform,
            external_conversation_id=message.external_conversation_id,
            external_message_id=message.external_message_id,
            send_status="handoff",
            agent_id="fake-agent",
            error_code="HANDOFF_REQUIRED",
            error_message=reason,
        )


def test_generic_web_chat_adapter_reads_context_and_dedupes_events():
    event = RawMessageEvent(
        platform="fake_platform",
        external_conversation_id="conv-1",
        external_message_id="msg-1",
        text="Is this item in stock?",
        customer_id="buyer-1",
        customer_name="Buyer One",
    )
    adapter = GenericWebChatAdapter(
        platform="fake_platform",
        watcher=FakeWatcher([event, event]),
        context_extractor=FakeContextExtractor(),
        executor=FakeExecutor(),
    )

    first_batch = adapter.read_new_messages()
    second_batch = adapter.read_new_messages()

    assert len(first_batch) == 1
    assert first_batch[0].platform == "fake_platform"
    assert first_batch[0].customer_message == "Is this item in stock?"
    assert first_batch[0].customer_id == "buyer-1"
    assert first_batch[0].page_context["product_name"] == "Adapter Test Product"
    assert first_batch[0].metadata["adapter"] == "GenericWebChatAdapter"
    assert second_batch == []


def test_generic_web_chat_adapter_delegates_send_and_handoff():
    event = RawMessageEvent(
        platform="fake_platform",
        external_conversation_id="conv-1",
        external_message_id="msg-1",
        text="Is this item in stock?",
    )
    executor = FakeExecutor()
    adapter = GenericWebChatAdapter(
        platform="fake_platform",
        watcher=FakeWatcher([event]),
        executor=executor,
    )
    message = adapter.read_new_messages()[0]

    send_result = adapter.send_text(message, "Yes, it is in stock.")
    handoff_result = adapter.mark_handoff(message, "Need manual review.")

    assert send_result.send_status == "success"
    assert handoff_result.send_status == "handoff"
    assert executor.sent == [("msg-1", "Yes, it is in stock.")]
    assert executor.handoffs == [("msg-1", "Need manual review.")]


def test_generic_web_chat_adapter_health_merges_watcher_state():
    adapter = GenericWebChatAdapter(
        platform="fake_platform",
        watcher=FakeWatcher([]),
        executor=FakeExecutor(),
    )

    health = adapter.health_check()

    assert health["status"] == "running"
    assert health["watched_window_title"] == "Fake Web Chat"
    assert health["platform"] == "fake_platform"
    assert health["adapter"] == "GenericWebChatAdapter"
    assert health["queued_messages"] == 0


def test_generic_web_chat_adapter_drains_messages_serially_by_conversation():
    events = [
        RawMessageEvent(
            platform="fake_platform",
            external_conversation_id="conv-1",
            external_message_id="msg-1",
            text="First conversation first message",
        ),
        RawMessageEvent(
            platform="fake_platform",
            external_conversation_id="conv-2",
            external_message_id="msg-2",
            text="Second conversation message",
        ),
        RawMessageEvent(
            platform="fake_platform",
            external_conversation_id="conv-1",
            external_message_id="msg-3",
            text="First conversation second message",
        ),
    ]
    adapter = GenericWebChatAdapter(
        platform="fake_platform",
        watcher=FakeWatcher(events),
        executor=FakeExecutor(),
    )

    messages = adapter.read_new_messages()

    assert [message.external_message_id for message in messages] == ["msg-1", "msg-3", "msg-2"]
