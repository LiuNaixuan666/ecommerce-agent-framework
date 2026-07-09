"""Tests for the platform registry and status API."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.storage.rpa_runtime_store import rpa_runtime_store

# Re-create store before each test
@pytest.fixture(autouse=True)
def reset_store():
    rpa_runtime_store.send_results.clear()
    rpa_runtime_store.agent_heartbeats.clear()
    yield


client = TestClient(app)


def seed_basic():
    """Seed minimum heartbeats for basic tests."""
    rpa_runtime_store.save_heartbeat({
        "agent_id": "test-pdd-agent-1",
        "merchant_id": "default",
        "platform": "pinduoduo",
        "status": "running",
        "watched_window_title": "拼多多客服工作台",
    })
    rpa_runtime_store.save_heartbeat({
        "agent_id": "test-pdd-agent-2",
        "merchant_id": "default",
        "platform": "pinduoduo",
        "status": "error",
        "error_code": "SELECTOR_NOT_FOUND",
        "error_message": "页面选择器不匹配",
    })
    rpa_runtime_store.save_send_result({
        "request_id": "test-req-1",
        "merchant_id": "default",
        "platform": "pinduoduo",
        "send_status": "success",
        "processing_status": "auto_sent",
        "customer_message": "这款有现货吗？",
        "sent_text": "亲，这款目前库存充足，可以放心下单哦～",
    })


class TestPlatformList:
    def test_list_platforms(self):
        """GET /api/platform/list returns platform registry with live status."""
        seed_basic()
        response = client.get("/api/platform/list")
        assert response.status_code == 200
        data = response.json()
        assert "platforms" in data
        assert data["total"] >= 5

        pdd = next((p for p in data["platforms"] if p["code"] == "pinduoduo"), None)
        assert pdd is not None
        assert pdd["name"] == "拼多多"
        assert pdd["status"] == "active"
        assert pdd["agent_count"] >= 2
        assert pdd["running_count"] >= 1
        assert pdd["error_count"] >= 1
        assert pdd["has_active_agent"] is True

        xianyu = next((p for p in data["platforms"] if p["code"] == "xianyu"), None)
        assert xianyu is not None
        assert xianyu["status"] == "coming_soon"
        assert xianyu["agent_count"] == 0

    def test_platform_colors_are_unique(self):
        """Each platform should have a defined color."""
        response = client.get("/api/platform/list")
        data = response.json()
        for p in data["platforms"]:
            assert p["color"] is not None
            assert len(p["color"]) > 0
            assert p["color"].startswith("#")


class TestPlatformStatus:
    def test_get_platform_status_active(self):
        """GET /api/platform/pinduoduo/status returns agent details and send results."""
        seed_basic()
        response = client.get("/api/platform/pinduoduo/status")
        assert response.status_code == 200
        data = response.json()
        assert data["platform"]["code"] == "pinduoduo"
        assert data["agent_count"] >= 2
        assert len(data["agents"]) >= 2
        assert data["send_result_count"] >= 1

        agent = data["agents"][0]
        assert "agent_id" in agent
        assert "status" in agent
        assert "last_heartbeat_at" in agent

    def test_monitoring_fields_present(self):
        """Agents with new monitoring fields should surface them."""
        rpa_runtime_store.save_heartbeat({
            "agent_id": "pdd-monitor-test",
            "merchant_id": "default",
            "platform": "pinduoduo",
            "status": "running",
            "latest_buyer_message": "老板，XL码有货吗？",
            "selector_profile": "pinduoduo_web.local",
            "current_page_url": "https://mms.pinduoduo.com/chat-merchant/index.html",
            "metadata": {
                "product_name": "夏季T恤",
                "sku": "SKU-001",
                "recommended_reply": "亲，有货哦～",
                "risk_level": "low",
                "auto_send_allowed": True,
            },
        })

        response = client.get("/api/platform/pinduoduo/status")
        assert response.status_code == 200
        data = response.json()

        agent = next((a for a in data["agents"] if a["agent_id"] == "pdd-monitor-test"), None)
        assert agent is not None
        assert agent["latest_buyer_message"] == "老板，XL码有货吗？"
        assert agent["selector_profile"] == "pinduoduo_web.local"
        assert agent["current_page_url"] == "https://mms.pinduoduo.com/chat-merchant/index.html"
        assert agent["metadata"]["product_name"] == "夏季T恤"
        assert agent["metadata"]["risk_level"] == "low"
        assert agent["metadata"]["auto_send_allowed"] is True

    def test_monitoring_fields_optional(self):
        """Agents without monitoring fields should have None."""
        rpa_runtime_store.save_heartbeat({
            "agent_id": "no-monitor",
            "merchant_id": "default",
            "platform": "pinduoduo",
            "status": "running",
        })
        response = client.get("/api/platform/pinduoduo/status")
        assert response.status_code == 200
        data = response.json()

        agent = next((a for a in data["agents"] if a["agent_id"] == "no-monitor"), None)
        assert agent is not None
        assert agent.get("latest_buyer_message") is None
        assert agent.get("selector_profile") is None
        assert agent.get("current_page_url") is None

    def test_get_platform_status_unknown(self):
        """GET /api/platform/unknown/status returns error message."""
        response = client.get("/api/platform/unknown/status")
        assert response.status_code == 200
        data = response.json()
        assert data["error"] is True
        assert "未知平台" in data["message"]

    def test_get_platform_status_coming_soon(self):
        """GET /api/platform/xianyu/status returns empty agents."""
        response = client.get("/api/platform/xianyu/status")
        assert response.status_code == 200
        data = response.json()
        assert data["platform"]["code"] == "xianyu"
        assert data["agent_count"] == 0
        assert data["send_result_count"] == 0


class TestSeedDemo:
    def test_seed_demo_creates_agents_and_results(self):
        """POST /api/local-agent/seed-demo injects demo heartbeats and send results."""
        response = client.post("/api/local-agent/seed-demo", json={"merchant_id": "default"})
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["agents_seeded"] == 3

        # Verify agents exist
        status_resp = client.get("/api/platform/pinduoduo/status")
        assert status_resp.status_code == 200
        pd = status_resp.json()
        assert pd["agent_count"] >= 3

        # Check monitoring fields on running agent
        agents = pd["agents"]
        running = next((a for a in agents if a["agent_id"] == "pdd-demo-running"), None)
        assert running is not None
        assert running["latest_buyer_message"] == "老板，这款衣服还有XL码吗？"
        assert running["selector_profile"] == "pinduoduo_web.local"
        assert running["metadata"]["product_name"] == "夏季纯棉休闲T恤"
        assert running["metadata"]["risk_level"] == "low"
        assert running["metadata"]["auto_send_allowed"] is True

        # Check send results seeded
        assert pd["send_result_count"] >= 2

    def test_seed_demo_default_merchant(self):
        """seed-demo works without merchant_id."""
        response = client.post("/api/local-agent/seed-demo", json={})
        assert response.status_code == 200
        data = response.json()
        assert data["agents_seeded"] == 3
        assert data["send_results_seeded"] == 2
