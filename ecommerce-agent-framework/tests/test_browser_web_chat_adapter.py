from app.local_agent.adapters.browser_web_chat import build_browser_web_chat_adapter
from app.local_agent.browser.selectors import BrowserChatSelectors


class FakeNode:
    def __init__(self, text="", attrs=None):
        self.text = text
        self.attrs = attrs or {}

    def inner_text(self):
        return self.text

    def get_attribute(self, name):
        return self.attrs.get(name)


class FakeLocator:
    def __init__(self, page, selector, nodes):
        self.page = page
        self.selector = selector
        self.nodes = nodes

    @property
    def first(self):
        return self.nth(0)

    def count(self):
        return len(self.nodes)

    def nth(self, index):
        return self.nodes[index]

    def fill(self, text):
        self.page.filled_text[self.selector] = text

    def click(self):
        self.page.clicks.append(self.selector)
        if self.selector == "[data-testid='send-button']":
            text = self.page.filled_text.get("[data-testid='reply-input']", "")
            self.page.add_sent_message(text)


class FakePage:
    def __init__(self):
        self.filled_text = {}
        self.clicks = []
        self.nodes = {
            "[data-testid='chat-root']": [FakeNode("root")],
            "[data-testid='reply-input']": [FakeNode("")],
            "[data-testid='send-button']": [FakeNode("send")],
            "[data-testid='buyer-message']": [
                FakeNode(
                    "Is this item in stock?",
                    {
                        "data-message-id": "msg-1",
                        "data-conversation-id": "conv-1",
                        "data-customer-id": "buyer-1",
                        "data-customer-name": "Buyer One",
                    },
                )
            ],
            "[data-testid='sent-message']": [],
            "[data-testid='product-name']": [FakeNode("Browser Test Product")],
            "[data-testid='sku']": [FakeNode("SKU-001")],
            "[data-testid='stock']": [FakeNode("12")],
        }

    def locator(self, selector):
        return FakeLocator(self, selector, self.nodes.get(selector, []))

    def title(self):
        return "Fake Browser Chat"

    def wait_for_timeout(self, timeout_ms):
        return None

    def add_sent_message(self, text):
        self.nodes["[data-testid='sent-message']"].append(FakeNode(text))


def selectors():
    return BrowserChatSelectors(
        root="[data-testid='chat-root']",
        buyer_messages="[data-testid='buyer-message']",
        reply_input="[data-testid='reply-input']",
        send_button="[data-testid='send-button']",
        sent_messages="[data-testid='sent-message']",
        product_fields={
            "product_name": "[data-testid='product-name']",
            "sku": "[data-testid='sku']",
            "stock": "[data-testid='stock']",
        },
    )


def test_browser_web_chat_adapter_reads_message_and_context():
    page = FakePage()
    adapter = build_browser_web_chat_adapter(
        page=page,
        platform="browser_mock",
        selectors=selectors(),
        agent_id="agent-browser-test",
    )

    messages = adapter.read_new_messages()

    assert adapter.detect_app() is True
    assert adapter.detect_login_status() is True
    assert len(messages) == 1
    assert messages[0].external_message_id == "msg-1"
    assert messages[0].external_conversation_id == "conv-1"
    assert messages[0].customer_message == "Is this item in stock?"
    assert messages[0].customer_id == "buyer-1"
    assert messages[0].customer_name == "Buyer One"
    assert messages[0].page_context["product_name"] == "Browser Test Product"
    assert messages[0].page_context["sku"] == "SKU-001"
    assert messages[0].page_context["stock"] == "12"


def test_browser_web_chat_adapter_reads_latest_message_by_default():
    page = FakePage()
    page.nodes["[data-testid='buyer-message']"].append(
        FakeNode(
            "Second buyer message",
            {
                "data-message-id": "msg-2",
                "data-conversation-id": "conv-1",
            },
        )
    )
    adapter = build_browser_web_chat_adapter(
        page=page,
        platform="browser_mock",
        selectors=selectors(),
        agent_id="agent-browser-test",
    )

    messages = adapter.read_new_messages()

    assert len(messages) == 1
    assert messages[0].external_message_id == "msg-2"
    assert messages[0].customer_message == "Second buyer message"
    assert messages[0].metadata["latest_only"] is True
    assert messages[0].metadata["dom_index"] == 1
    assert messages[0].metadata["dom_count"] == 2


def test_browser_web_chat_adapter_can_read_all_visible_messages_for_debugging():
    page = FakePage()
    page.nodes["[data-testid='buyer-message']"].append(
        FakeNode(
            "Second buyer message",
            {
                "data-message-id": "msg-2",
                "data-conversation-id": "conv-1",
            },
        )
    )
    adapter = build_browser_web_chat_adapter(
        page=page,
        platform="browser_mock",
        selectors=selectors(),
        agent_id="agent-browser-test",
        latest_only=False,
    )

    messages = adapter.read_new_messages()

    assert [message.external_message_id for message in messages] == ["msg-1", "msg-2"]


def test_browser_web_chat_adapter_fills_sends_and_verifies_reply():
    page = FakePage()
    adapter = build_browser_web_chat_adapter(
        page=page,
        platform="browser_mock",
        selectors=selectors(),
        agent_id="agent-browser-test",
    )
    message = adapter.read_new_messages()[0]

    result = adapter.send_text(message, "Yes, it is in stock.")

    assert result.send_status == "success"
    assert result.sent_text == "Yes, it is in stock."
    assert result.agent_id == "agent-browser-test"
    assert page.filled_text["[data-testid='reply-input']"] == "Yes, it is in stock."
    assert page.clicks == ["[data-testid='send-button']"]
    assert page.nodes["[data-testid='sent-message']"][0].inner_text() == "Yes, it is in stock."


def test_browser_web_chat_adapter_reports_failed_when_send_is_not_verified():
    page = FakePage()
    page.nodes["[data-testid='send-button']"] = [FakeNode("send")]

    def no_sent_message(text):
        return None

    page.add_sent_message = no_sent_message
    adapter = build_browser_web_chat_adapter(
        page=page,
        platform="browser_mock",
        selectors=selectors(),
        agent_id="agent-browser-test",
    )
    message = adapter.read_new_messages()[0]

    result = adapter.send_text(message, "Yes, it is in stock.")

    assert result.send_status == "failed"
    assert result.error_code == "SEND_NOT_VERIFIED"


def test_browser_web_chat_adapter_dry_run_does_not_fill_or_click():
    page = FakePage()
    adapter = build_browser_web_chat_adapter(
        page=page,
        platform="browser_mock",
        selectors=selectors(),
        agent_id="agent-browser-test",
        dry_run=True,
    )
    message = adapter.read_new_messages()[0]

    result = adapter.send_text(message, "Yes, it is in stock.")

    assert result.send_status == "skipped_dry_run"
    assert result.error_code == "DRY_RUN"
    assert result.metadata["dry_run"] is True
    assert page.filled_text == {}
    assert page.clicks == []
