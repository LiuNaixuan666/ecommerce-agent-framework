import json

import pytest

from app.local_agent.browser.profiles import get_builtin_profile, load_profile_from_json


def test_builtin_browser_mock_profile_points_to_local_mock_page():
    profile = get_builtin_profile("browser_mock")

    assert profile.name == "browser_mock"
    assert profile.platform == "browser_mock"
    assert profile.default_url.startswith("file:///")
    assert profile.selectors.root == "[data-testid='chat-root']"
    assert profile.selectors.product_fields["product_name"] == "[data-testid='product-name']"


def test_load_browser_profile_from_json(tmp_path):
    path = tmp_path / "custom_profile.json"
    path.write_text(
        json.dumps(
            {
                "name": "custom_platform",
                "platform": "custom",
                "default_url": "https://example.test/chat",
                "default_conversation_id": "custom-conv",
                "selectors": {
                    "root": "#app",
                    "buyer_messages": ".buyer",
                    "reply_input": "textarea",
                    "send_button": "button.send",
                    "sent_messages": ".sent",
                    "message_id_attr": "data-id",
                    "product_fields": {"product_name": ".title"},
                },
            }
        ),
        encoding="utf-8",
    )

    profile = load_profile_from_json(path)

    assert profile.name == "custom_platform"
    assert profile.platform == "custom"
    assert profile.default_url == "https://example.test/chat"
    assert profile.default_conversation_id == "custom-conv"
    assert profile.selectors.message_id_attr == "data-id"
    assert profile.selectors.product_fields == {"product_name": ".title"}


def test_load_browser_profile_rejects_missing_required_selector(tmp_path):
    path = tmp_path / "bad_profile.json"
    path.write_text(
        json.dumps(
            {
                "name": "bad",
                "selectors": {
                    "root": "#app",
                    "buyer_messages": ".buyer",
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required selectors"):
        load_profile_from_json(path)
