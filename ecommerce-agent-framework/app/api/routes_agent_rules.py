"""API routes for AI handoff and auto-send rule configuration."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.storage.agent_rule_store import agent_rule_store

router = APIRouter(prefix="/api/agent-rules", tags=["agent-rules"])


class HandoffRules(BaseModel):
    keyword: bool = True
    image: bool = True
    after_sale: bool = True
    out_of_knowledge: bool = True
    low_confidence: bool = True
    timeout: bool = True


class AgentRuleConfig(BaseModel):
    model_config = ConfigDict(extra="allow")

    merchant_id: str = "default"
    platform: str = "pinduoduo"
    mode: Literal["dry_run", "assist", "auto"] = "dry_run"
    auto_send_low_risk: bool = False
    confidence_threshold: float = Field(0.75, ge=0, le=1)
    handoff_rules: HandoffRules = Field(default_factory=HandoffRules)
    sensitive_words: List[str] = Field(default_factory=list)
    handoff_keywords: List[str] = Field(default_factory=list)
    timeout_seconds: int = Field(180, ge=30)
    fallback_script: str = "亲，请稍等，这个问题为您转接人工客服确认。"

@router.get("")
async def get_agent_rules(
    merchant_id: str = Query("default"),
    platform: str = Query("pinduoduo"),
) -> Dict[str, Any]:
    return {"rules": agent_rule_store.get_rules(merchant_id=merchant_id, platform=platform)}


@router.put("")
async def save_agent_rules(config: AgentRuleConfig) -> Dict[str, Any]:
    try:
        saved = agent_rule_store.save_rules(config.model_dump())
        return {"status": "ok", "rules": saved}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"保存规则失败: {exc}")


@router.get("/list")
async def list_agent_rules(merchant_id: Optional[str] = None) -> Dict[str, Any]:
    rules = agent_rule_store.list_rules(merchant_id=merchant_id)
    return {"total": len(rules), "rules": rules}
