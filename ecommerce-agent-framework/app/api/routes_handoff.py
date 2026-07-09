"""Handoff ticket API routes.

Provides persistent handoff queue management:
  - List / filter tickets
  - Create tickets (used internally by routes_chat)
  - Start processing, resolve, return-to-ai, close
  - Summary counts for platform badge notifications
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.storage.handoff_store import (
    HANDOFF_STATUS_CLOSED,
    HANDOFF_STATUS_PENDING,
    HANDOFF_STATUS_PROCESSING,
    HANDOFF_STATUS_RESOLVED,
    HANDOFF_STATUS_RETURNED_TO_AI,
    handoff_store,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/handoff", tags=["handoff"])


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class CreateTicketRequest(BaseModel):
    merchant_id: Optional[str] = "default"
    platform: str = Field(..., min_length=1)
    conversation_id: Optional[str] = None
    external_conversation_id: Optional[str] = None
    external_message_id: Optional[str] = None
    customer_message: str = ""
    recommended_reply: Optional[str] = None
    reason: Optional[str] = None
    blockers: List[str] = Field(default_factory=list)
    risk_level: Optional[str] = None
    confidence: Optional[float] = None
    source: Optional[str] = "api"


class UpdateStatusRequest(BaseModel):
    human_reply: Optional[str] = None
    assigned_to: Optional[str] = None


class TicketResponse(BaseModel):
    ticket_id: str
    merchant_id: str
    platform: str
    conversation_id: str
    external_conversation_id: str
    external_message_id: str
    customer_message: str
    recommended_reply: str
    reason: str
    blockers: List[str]
    risk_level: str
    confidence: Optional[float] = None
    status: str
    assigned_to: Optional[str] = None
    human_reply: Optional[str] = None
    created_at: str
    updated_at: str
    resolved_at: Optional[str] = None
    returned_to_ai_at: Optional[str] = None
    duplicate_count: int = 0
    source: str = ""


class TicketListResponse(BaseModel):
    total: int
    tickets: List[TicketResponse]


class SummaryResponse(BaseModel):
    platforms: Dict[str, Dict[str, int]]
    total_pending: int
    total_processing: int
    total_active: int


class CreateTicketResponse(BaseModel):
    status: str = "ok"
    ticket: TicketResponse
    created: bool = True


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _ticket_to_response(ticket: Dict[str, Any]) -> TicketResponse:
    return TicketResponse(
        ticket_id=ticket.get("ticket_id", ""),
        merchant_id=ticket.get("merchant_id", "default"),
        platform=ticket.get("platform", ""),
        conversation_id=ticket.get("conversation_id", ""),
        external_conversation_id=ticket.get("external_conversation_id", ""),
        external_message_id=ticket.get("external_message_id", ""),
        customer_message=ticket.get("customer_message", ""),
        recommended_reply=ticket.get("recommended_reply", ""),
        reason=ticket.get("reason", ""),
        blockers=list(ticket.get("blockers") or []),
        risk_level=ticket.get("risk_level", ""),
        confidence=ticket.get("confidence"),
        status=ticket.get("status", HANDOFF_STATUS_PENDING),
        assigned_to=ticket.get("assigned_to"),
        human_reply=ticket.get("human_reply"),
        created_at=ticket.get("created_at", ""),
        updated_at=ticket.get("updated_at", ""),
        resolved_at=ticket.get("resolved_at"),
        returned_to_ai_at=ticket.get("returned_to_ai_at"),
        duplicate_count=ticket.get("duplicate_count", 0),
        source=ticket.get("source", ""),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/tickets", response_model=TicketListResponse)
async def list_tickets(
    merchant_id: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> TicketListResponse:
    """List handoff tickets with optional filters."""
    try:
        tickets = handoff_store.list_tickets(
            merchant_id=merchant_id,
            platform=platform,
            status=status,
            limit=limit,
        )
        return TicketListResponse(
            total=len(tickets),
            tickets=[_ticket_to_response(t) for t in tickets],
        )
    except Exception as exc:
        logger.exception("Error listing handoff tickets: %s", exc)
        raise HTTPException(status_code=500, detail=f"获取待人工列表失败: {exc}")


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str) -> TicketResponse:
    """Get a single handoff ticket by ID."""
    try:
        ticket = handoff_store.get_ticket(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"待人工 ticket {ticket_id} 不存在")
        return _ticket_to_response(ticket)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error getting handoff ticket %s: %s", ticket_id, exc)
        raise HTTPException(status_code=500, detail=f"获取待人工 ticket 失败: {exc}")


@router.post("/tickets", response_model=CreateTicketResponse)
async def create_ticket(request: CreateTicketRequest) -> CreateTicketResponse:
    """Create a handoff ticket (or return existing duplicate)."""
    try:
        merchant_id = request.merchant_id or "default"
        payload: Dict[str, Any] = {
            "merchant_id": merchant_id,
            "platform": request.platform,
            "conversation_id": request.conversation_id or "",
            "external_conversation_id": request.external_conversation_id or "",
            "external_message_id": request.external_message_id,
            "customer_message": request.customer_message,
            "recommended_reply": request.recommended_reply or "",
            "reason": request.reason or "",
            "blockers": request.blockers,
            "risk_level": request.risk_level or "",
            "confidence": request.confidence,
            "source": request.source or "api",
        }
        ticket = handoff_store.create_ticket(payload)
        return CreateTicketResponse(
            ticket=_ticket_to_response(ticket),
            created=ticket.get("duplicate_count", 0) == 0,
        )
    except Exception as exc:
        logger.exception("Error creating handoff ticket: %s", exc)
        raise HTTPException(status_code=500, detail=f"创建待人工 ticket 失败: {exc}")


@router.post("/tickets/{ticket_id}/start", response_model=TicketResponse)
async def start_processing(ticket_id: str,
                           body: Optional[UpdateStatusRequest] = None) -> TicketResponse:
    """Mark a ticket as being processed by a human."""
    try:
        extra: Dict[str, Any] = {}
        if body and body.assigned_to:
            extra["assigned_to"] = body.assigned_to
        ticket = handoff_store.update_status(ticket_id, HANDOFF_STATUS_PROCESSING, **extra)
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"待人工 ticket {ticket_id} 不存在")
        return _ticket_to_response(ticket)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error starting handoff ticket %s: %s", ticket_id, exc)
        raise HTTPException(status_code=500, detail=f"标记处理中失败: {exc}")


@router.post("/tickets/{ticket_id}/resolve", response_model=TicketResponse)
async def resolve_ticket(ticket_id: str,
                         body: Optional[UpdateStatusRequest] = None) -> TicketResponse:
    """Mark a ticket as resolved (human has handled it)."""
    try:
        extra: Dict[str, Any] = {}
        if body and body.human_reply:
            extra["human_reply"] = body.human_reply
        ticket = handoff_store.update_status(ticket_id, HANDOFF_STATUS_RESOLVED, **extra)
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"待人工 ticket {ticket_id} 不存在")
        return _ticket_to_response(ticket)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error resolving handoff ticket %s: %s", ticket_id, exc)
        raise HTTPException(status_code=500, detail=f"标记已处理失败: {exc}")


@router.post("/tickets/{ticket_id}/return-to-ai", response_model=TicketResponse)
async def return_to_ai(ticket_id: str) -> TicketResponse:
    """Return a ticket back to AI handling."""
    try:
        ticket = handoff_store.update_status(ticket_id, HANDOFF_STATUS_RETURNED_TO_AI)
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"待人工 ticket {ticket_id} 不存在")
        return _ticket_to_response(ticket)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error returning handoff ticket %s to AI: %s", ticket_id, exc)
        raise HTTPException(status_code=500, detail=f"转回 AI 失败: {exc}")


@router.post("/tickets/{ticket_id}/close", response_model=TicketResponse)
async def close_ticket(ticket_id: str) -> TicketResponse:
    """Close a ticket manually."""
    try:
        ticket = handoff_store.update_status(ticket_id, HANDOFF_STATUS_CLOSED)
        if ticket is None:
            raise HTTPException(status_code=404, detail=f"待人工 ticket {ticket_id} 不存在")
        return _ticket_to_response(ticket)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error closing handoff ticket %s: %s", ticket_id, exc)
        raise HTTPException(status_code=500, detail=f"关闭 ticket 失败: {exc}")


@router.get("/summary", response_model=SummaryResponse)
async def get_summary(merchant_id: Optional[str] = Query(None)) -> SummaryResponse:
    """Return pending/processing counts grouped by platform for badge display.

    Frontend uses this to show red dots on the left platform panel.
    """
    try:
        summary = handoff_store.get_summary(merchant_id=merchant_id)
        return SummaryResponse(**summary)
    except Exception as exc:
        logger.exception("Error getting handoff summary: %s", exc)
        raise HTTPException(status_code=500, detail=f"获取待人工汇总失败: {exc}")
