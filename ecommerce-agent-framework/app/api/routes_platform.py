"""Platform registry and status aggregation for the multi-platform console.

Provides an API for the frontend to discover which platforms are registered,
what their status is, and aggregate agent heartbeat data per platform.
"""

from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.storage.rpa_runtime_store import rpa_runtime_store

router = APIRouter(prefix="/api/platform", tags=["platform"])

# ---------------------------------------------------------------------------
# Platform registry — the canonical list of platforms the system knows about
# ---------------------------------------------------------------------------
PLATFORM_REGISTRY = [
    {
        "code": "pinduoduo",
        "name": "拼多多",
        "icon": "pdd",
        "color": "#E02E24",
        "order": 1,
        "status": "active",       # active | beta | coming_soon
        "description": "拼多多商家客服工作台",
    },
    {
        "code": "xianyu",
        "name": "闲鱼",
        "icon": "xianyu",
        "color": "#FF6A00",
        "order": 2,
        "status": "coming_soon",
        "description": "闲鱼平台客服（即将接入）",
    },
    {
        "code": "taobao",
        "name": "淘宝 / 千牛",
        "icon": "taobao",
        "color": "#FF4400",
        "order": 3,
        "status": "coming_soon",
        "description": "淘宝 / 千牛卖家工作台（即将接入）",
    },
    {
        "code": "jd",
        "name": "京东",
        "icon": "jd",
        "color": "#E2231A",
        "order": 4,
        "status": "coming_soon",
        "description": "京东商家客服（即将接入）",
    },
    {
        "code": "douyin",
        "name": "抖店",
        "icon": "douyin",
        "color": "#000000",
        "order": 5,
        "status": "coming_soon",
        "description": "抖音电商客服（即将接入）",
    },
]

# Map platform codes to display colors for agent badges
PLATFORM_COLORS = {p["code"]: p["color"] for p in PLATFORM_REGISTRY}


@router.get("/list")
async def list_platforms():
    """Return the platform registry with live agent status merged in."""
    agents = rpa_runtime_store.list_agent_status()
    # Group agent heartbeats by platform
    agents_by_platform: dict = {}
    for agent in agents:
        p = agent.get("platform", "unknown")
        agents_by_platform.setdefault(p, []).append(agent)

    platforms = []
    for pdef in PLATFORM_REGISTRY:
        code = pdef["code"]
        platform_agents = agents_by_platform.get(code, [])
        running_agents = [a for a in platform_agents if a.get("status") == "running"]
        error_agents = [a for a in platform_agents if a.get("status") == "error"]

        platforms.append({
            **pdef,
            "agent_count": len(platform_agents),
            "running_count": len(running_agents),
            "error_count": len(error_agents),
            "has_active_agent": len(running_agents) > 0,
            "latest_heartbeat_at": max(
                (a.get("last_heartbeat_at", "") for a in platform_agents),
                default=None,
            ),
        })

    return {"platforms": platforms, "total": len(platforms)}


@router.get("/{platform_code}/status")
async def get_platform_status(platform_code: str):
    """Return detailed status for a specific platform, including agent heartbeats."""
    pdef = next((p for p in PLATFORM_REGISTRY if p["code"] == platform_code), None)
    if not pdef:
        return {"error": True, "message": f"未知平台: {platform_code}"}

    agents = rpa_runtime_store.list_agent_status(platform=platform_code)
    send_results = rpa_runtime_store.list_send_results(platform=platform_code, limit=20)

    return {
        "platform": pdef,
        "agents": agents,
        "agent_count": len(agents),
        "recent_send_results": send_results,
        "send_result_count": len(send_results),
    }
