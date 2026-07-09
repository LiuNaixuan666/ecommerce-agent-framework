"""Local Agent runtime API routes."""

from datetime import datetime
import logging
from typing import Any, Dict, Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.storage.rpa_runtime_store import rpa_runtime_store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/local-agent", tags=["local-agent"])


class LocalAgentHeartbeatRequest(BaseModel):
    agent_id: str = Field(..., min_length=1)
    merchant_id: Optional[str] = "default"
    platform: Optional[str] = None
    shop_id: Optional[str] = None
    status: Literal["running", "paused", "stopped", "error"] = "running"
    watched_window_title: Optional[str] = None
    last_message_seen_at: Optional[datetime] = None
    last_send_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    # Live monitoring fields (Stage 6: 拼多多工作台 MVP)
    latest_buyer_message: Optional[str] = None
    selector_profile: Optional[str] = None
    current_page_url: Optional[str] = None

    metadata: Optional[Dict[str, Any]] = None


class LocalAgentHeartbeatResponse(BaseModel):
    status: str = "ok"
    agent_status: Dict[str, Any]


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


@router.post("/heartbeat", response_model=LocalAgentHeartbeatResponse)
async def local_agent_heartbeat(request: LocalAgentHeartbeatRequest) -> LocalAgentHeartbeatResponse:
    """Record the latest runtime status reported by a Local Agent."""

    try:
        payload = _json_ready(request.model_dump(exclude_none=True))
        payload["merchant_id"] = request.merchant_id or "default"
        agent_status = rpa_runtime_store.save_heartbeat(payload)
        return LocalAgentHeartbeatResponse(agent_status=agent_status)
    except Exception as exc:
        logger.exception("Error in local_agent_heartbeat: %s", exc)
        raise HTTPException(status_code=500, detail=f"Local Agent 心跳记录失败: {exc}")


@router.get("/status")
async def list_local_agent_status(
    merchant_id: Optional[str] = None,
    platform: Optional[str] = None,
) -> Dict[str, Any]:
    statuses = rpa_runtime_store.list_agent_status(merchant_id=merchant_id, platform=platform)
    return {
        "total": len(statuses),
        "agents": statuses,
    }


@router.get("/status/{agent_id}")
async def get_local_agent_status(agent_id: str) -> Dict[str, Any]:
    agent_status = rpa_runtime_store.get_agent_status(agent_id)
    if not agent_status:
        raise HTTPException(status_code=404, detail=f"Local Agent {agent_id} 不存在")
    return agent_status


# ---------------------------------------------------------------------------
# Demo / seed helper (development only)
# ---------------------------------------------------------------------------

class SeedDemoRequest(BaseModel):
    merchant_id: Optional[str] = "default"


@router.post("/seed-demo", include_in_schema=False)
async def seed_demo_data(request: SeedDemoRequest):
    """Inject demo heartbeats and send results for development/testing."""
    now = datetime.now()
    mid = request.merchant_id or "default"

    rpa_runtime_store.save_heartbeat({
        "agent_id": "pdd-demo-running",
        "merchant_id": mid,
        "platform": "pinduoduo",
        "shop_id": "pdd_shop_001",
        "status": "running",
        "watched_window_title": "拼多多商家后台 - 客服工作台",
        "last_message_seen_at": now.isoformat(),
        "last_send_at": now.isoformat(),
        "latest_buyer_message": "老板，这款衣服还有XL码吗？",
        "selector_profile": "pinduoduo_web.local",
        "current_page_url": "https://mms.pinduoduo.com/chat-merchant/index.html",
        "metadata": {
            "product_name": "夏季纯棉休闲T恤",
            "sku": "SKU-TEE-2024-XL",
            "product_price": "89.00",
            "stock": 15,
            "recommended_reply": "亲，XL码库存还有15件，目前有满199减30活动，可以放心下单哦～",
            "risk_level": "low",
            "auto_send_allowed": True,
            "auto_send_blockers": [],
            "intent": "PRODUCT_INQUIRY",
            "confidence": 0.92,
        },
    })

    rpa_runtime_store.save_heartbeat({
        "agent_id": "pdd-demo-idle",
        "merchant_id": mid,
        "platform": "pinduoduo",
        "shop_id": "pdd_shop_001",
        "status": "running",
        "watched_window_title": "拼多多商家后台 - 客服工作台",
        "latest_buyer_message": None,
        "selector_profile": "pinduoduo_web.local",
        "current_page_url": "https://mms.pinduoduo.com/chat-merchant/index.html",
        "metadata": {
            "status": "waiting",
            "recommended_reply": None,
        },
    })

    rpa_runtime_store.save_heartbeat({
        "agent_id": "pdd-demo-error",
        "merchant_id": mid,
        "platform": "pinduoduo",
        "status": "error",
        "error_code": "SELECTOR_NOT_FOUND",
        "error_message": "页面选择器不匹配：未找到 div.buyer-item",
        "selector_profile": "pinduoduo_web.local",
        "current_page_url": "https://mms.pinduoduo.com/chat-merchant/index.html",
    })

    # Seed some send results
    rpa_runtime_store.save_send_result({
        "request_id": f"demo-sr-1",
        "merchant_id": mid,
        "platform": "pinduoduo",
        "external_conversation_id": "conv-demo-001",
        "external_message_id": "msg-demo-001",
        "send_status": "success",
        "processing_status": "auto_sent",
        "customer_message": "这款还有XL码吗？",
        "sent_text": "亲，XL码库存还有15件，目前有满199减30活动，可以放心下单哦～",
        "agent_id": "pdd-demo-running",
    })

    rpa_runtime_store.save_send_result({
        "request_id": f"demo-sr-2",
        "merchant_id": mid,
        "platform": "pinduoduo",
        "external_conversation_id": "conv-demo-002",
        "external_message_id": "msg-demo-002",
        "send_status": "handoff",
        "processing_status": "handoff_required",
        "customer_message": "我要退货退款",
        "sent_text": None,
        "agent_id": "pdd-demo-running",
    })

    return {
        "status": "ok",
        "message": "Demo data seeded",
        "agents_seeded": 3,
        "send_results_seeded": 2,
    }
