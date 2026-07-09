"""Chat API routes.

This module keeps HTTP concerns thin: conversation storage, request/response
models, webhook delegation, and health/history endpoints. The customer-service
business flow lives in app.agent.workflow.
"""

from datetime import datetime
import logging
import uuid
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.agent.workflow import default_workflow
from app.connectors.chat_manager import chat_manager
from app.models.schemas import ConversationHistoryResponse
from app.storage.agent_rule_store import agent_rule_store
from app.storage.handoff_store import handoff_store
from app.storage.rpa_runtime_store import rpa_runtime_store
from app.storage.storage_manager import storage_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


def _create_conversation_id() -> str:
    return str(uuid.uuid4())


def _create_stable_rpa_conversation_id(merchant_id: str, platform: str, external_conversation_id: str) -> str:
    raw_key = f"rpa:{merchant_id}:{platform}:{external_conversation_id}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw_key))


def _json_ready(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_ready(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_ready(item) for item in value]
    return value


def _get_or_create_conversation(conversation_id: Optional[str] = None, merchant_id: Optional[str] = None) -> str:
    if conversation_id:
        existing = storage_manager.get_conversation(conversation_id)
        if existing:
            return conversation_id

    new_id = _create_conversation_id()
    now = datetime.now().isoformat()
    conversation_data = {
        "conversation_id": new_id,
        "merchant_id": merchant_id,
        "created_at": now,
        "last_updated": now,
        "last_intent": None,
        "status": "active",
        "message_count": 0,
    }
    storage_manager.save_conversation(new_id, conversation_data)
    storage_manager.save_conversation_metadata(conversation_data)
    return new_id


def _get_or_create_rpa_conversation(
    merchant_id: str,
    platform: str,
    external_conversation_id: str,
    customer_id: Optional[str] = None,
    customer_name: Optional[str] = None,
) -> str:
    conversation_id = _create_stable_rpa_conversation_id(merchant_id, platform, external_conversation_id)
    existing = storage_manager.get_conversation(conversation_id)
    if existing:
        updates: Dict[str, Any] = {
            "last_updated": datetime.now().isoformat(),
            "rpa_platform": platform,
            "rpa_external_conversation_id": external_conversation_id,
        }
        if customer_id:
            updates["customer_id"] = customer_id
        if customer_name:
            updates["customer_name"] = customer_name
        existing.update(updates)
        storage_manager.save_conversation(conversation_id, existing)
        storage_manager.update_conversation_metadata(conversation_id, updates)
        return conversation_id

    now = datetime.now().isoformat()
    conversation_data = {
        "conversation_id": conversation_id,
        "merchant_id": merchant_id,
        "created_at": now,
        "last_updated": now,
        "last_intent": None,
        "status": "active",
        "message_count": 0,
        "source": "rpa",
        "rpa_platform": platform,
        "rpa_external_conversation_id": external_conversation_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "rpa_processed_events": {},
    }
    storage_manager.save_conversation(conversation_id, conversation_data)
    storage_manager.save_conversation_metadata(conversation_data)
    return conversation_id


def _add_message_to_conversation(
    conversation_id: str,
    role: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }
    if metadata:
        message["metadata"] = metadata
    storage_manager.add_message(conversation_id, message)

    conversation_data = storage_manager.get_conversation(conversation_id)
    if not conversation_data:
        return

    conversation_data["last_updated"] = datetime.now().isoformat()
    conversation_data["message_count"] = conversation_data.get("message_count", 0) + 1
    storage_manager.save_conversation(conversation_id, conversation_data)
    storage_manager.update_conversation_metadata(
        conversation_id,
        {
            "last_updated": conversation_data["last_updated"],
            "message_count": conversation_data["message_count"],
        },
    )


def _get_conversation_history(conversation_id: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
    return storage_manager.get_messages(conversation_id, limit, offset)


def _workflow_message_metadata(workflow_result: Any, **extra: Any) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "intent": getattr(workflow_result, "intent", None),
        "confidence": getattr(workflow_result, "confidence", None),
        "sources": getattr(workflow_result, "sources", []) or [],
        "retrieval_type": getattr(workflow_result, "retrieval_type", None),
        "evidence_sources": getattr(workflow_result, "evidence_sources", []) or [],
        "risk_level": getattr(workflow_result, "risk_level", None),
        "auto_send_allowed": bool(getattr(workflow_result, "auto_send_allowed", False)),
        "auto_send_blockers": getattr(workflow_result, "auto_send_blockers", []) or [],
        "requires_human_review": bool(getattr(workflow_result, "requires_human_review", False)),
    }
    metadata.update(extra)
    return _json_ready(metadata)


class ChatRequest(BaseModel):
    merchant_id: Optional[str] = "default"
    user_query: str
    conversation_history: Optional[List[dict]] = None
    conversation_id: Optional[str] = None
    page_context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    merchant_id: str
    user_query: str
    response_text: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    sources: Optional[List[str]] = None
    is_clarification_triggered: bool = False
    recommended_reply: Optional[str] = None
    risk_level: Optional[str] = None
    auto_send_allowed: bool = False
    auto_send_blockers: Optional[List[str]] = None
    requires_human_review: bool = False
    handoff_reason: Optional[str] = None
    missing_info: Optional[List[str]] = None
    retrieval_type: Optional[str] = None
    evidence_sources: Optional[List[Dict[str, Any]]] = None
    conversation_id: Optional[str] = None
    timestamp: datetime


class RpaPageContext(BaseModel):
    model_config = ConfigDict(extra="allow")

    platform: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    product_name: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[Any] = None
    currency: Optional[str] = "CNY"
    stock: Optional[Any] = None
    inventory: Optional[Any] = None
    stock_status: Optional[str] = None

class RpaMessageRequest(BaseModel):
    merchant_id: Optional[str] = "default"
    platform: str = Field(..., min_length=1)
    external_conversation_id: str = Field(..., min_length=1)
    customer_message: str = Field(..., min_length=1)
    external_message_id: Optional[str] = None
    customer_id: Optional[str] = None
    customer_name: Optional[str] = None
    page_context: Optional[RpaPageContext] = None
    metadata: Optional[Dict[str, Any]] = None
    received_at: Optional[datetime] = None


class RpaMessageInfo(BaseModel):
    external_message_id: Optional[str] = None
    customer_message: str
    duplicate_event: bool = False


class RpaReplyPayload(BaseModel):
    recommended_reply: str
    send_text: Optional[str] = None


class RpaDecisionPayload(BaseModel):
    action: str
    auto_send_allowed: bool
    risk_level: Optional[str] = None
    confidence: Optional[float] = None
    auto_send_blockers: List[str] = Field(default_factory=list)
    requires_human_review: bool = False
    handoff_reason: Optional[str] = None
    missing_info: List[str] = Field(default_factory=list)


class RpaTracePayload(BaseModel):
    intent: Optional[str] = None
    retrieval_type: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    evidence_sources: List[Dict[str, Any]] = Field(default_factory=list)


class RpaInstructionPayload(BaseModel):
    should_send: bool
    should_handoff: bool
    send_text: Optional[str] = None
    handoff_note: Optional[str] = None


class RpaMessageResponse(BaseModel):
    schema_version: str = "rpa.message.v1"
    request_id: str
    merchant_id: str
    platform: str
    external_conversation_id: str
    conversation_id: str
    received_at: datetime
    processed_at: datetime
    message: RpaMessageInfo
    reply: RpaReplyPayload
    decision: RpaDecisionPayload
    trace: RpaTracePayload
    rpa_instruction: RpaInstructionPayload


class RpaSendResultRequest(BaseModel):
    request_id: str = Field(..., min_length=1)
    merchant_id: Optional[str] = "default"
    platform: str = Field(..., min_length=1)
    external_conversation_id: str = Field(..., min_length=1)
    external_message_id: Optional[str] = None
    customer_message: Optional[str] = None
    send_status: Literal["success", "failed", "handoff", "skipped_duplicate", "skipped_stale", "skipped_dry_run"]
    sent_text: Optional[str] = None
    sent_at: Optional[datetime] = None
    agent_id: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class RpaSendResultResponse(BaseModel):
    status: str = "ok"
    conversation_id: str
    send_result: Dict[str, Any]


def _processing_status_from_send_status(send_status: str) -> str:
    mapping = {
        "success": "auto_sent",
        "failed": "send_failed",
        "handoff": "handoff_required",
        "skipped_duplicate": "skipped_duplicate",
        "skipped_stale": "skipped_stale",
        "skipped_dry_run": "skipped_dry_run",
    }
    return mapping.get(send_status, "unknown")


def _build_rpa_response_payload(
    *,
    request_id: str,
    request: RpaMessageRequest,
    conversation_id: str,
    workflow_result: Any,
    duplicate_event: bool = False,
) -> Dict[str, Any]:
    auto_send_allowed = bool(workflow_result.auto_send_allowed)
    recommended_reply = workflow_result.response_text
    action = "send" if auto_send_allowed else "handoff"
    handoff_note = workflow_result.handoff_reason
    if not handoff_note and workflow_result.auto_send_blockers:
        handoff_note = "blocked_by_policy: " + ", ".join(workflow_result.auto_send_blockers)

    return {
        "schema_version": "rpa.message.v1",
        "request_id": request_id,
        "merchant_id": request.merchant_id or "default",
        "platform": request.platform,
        "external_conversation_id": request.external_conversation_id,
        "conversation_id": conversation_id,
        "received_at": request.received_at or datetime.now(),
        "processed_at": datetime.now(),
        "message": {
            "external_message_id": request.external_message_id,
            "customer_message": request.customer_message,
            "duplicate_event": duplicate_event,
        },
        "reply": {
            "recommended_reply": recommended_reply,
            "send_text": recommended_reply if auto_send_allowed else None,
        },
        "decision": {
            "action": action,
            "auto_send_allowed": auto_send_allowed,
            "risk_level": workflow_result.risk_level,
            "confidence": workflow_result.confidence,
            "auto_send_blockers": workflow_result.auto_send_blockers,
            "requires_human_review": workflow_result.requires_human_review,
            "handoff_reason": workflow_result.handoff_reason,
            "missing_info": workflow_result.missing_info,
        },
        "trace": {
            "intent": workflow_result.intent,
            "retrieval_type": workflow_result.retrieval_type,
            "sources": workflow_result.sources,
            "evidence_sources": getattr(workflow_result, "evidence_sources", []),
        },
        "rpa_instruction": {
            "should_send": auto_send_allowed,
            "should_handoff": not auto_send_allowed,
            "send_text": recommended_reply if auto_send_allowed else None,
            "handoff_note": handoff_note,
        },
    }


def _remember_rpa_event(conversation_id: str, external_message_id: Optional[str], payload: Dict[str, Any]) -> None:
    if not external_message_id:
        return
    conversation_data = storage_manager.get_conversation(conversation_id)
    if not conversation_data:
        return
    processed_events = conversation_data.get("rpa_processed_events") or {}
    processed_events[external_message_id] = _json_ready(payload)
    if len(processed_events) > 50:
        processed_events = dict(list(processed_events.items())[-50:])
    conversation_data["rpa_processed_events"] = processed_events
    conversation_data["last_updated"] = datetime.now().isoformat()
    storage_manager.save_conversation(conversation_id, conversation_data)


@router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest) -> ChatResponse:
    """Run the current customer-service workflow for a user query."""

    try:
        merchant_id = request.merchant_id or "default"
        user_query = request.user_query.strip()
        if not user_query:
            raise HTTPException(status_code=400, detail="user_query cannot be empty")

        conversation_id = _get_or_create_conversation(
            conversation_id=request.conversation_id,
            merchant_id=merchant_id,
        )
        _add_message_to_conversation(conversation_id, "user", user_query)

        workflow_history = request.conversation_history or _get_conversation_history(conversation_id, limit=10)
        platform = "pinduoduo"
        if request.page_context and request.page_context.get("platform"):
            platform = str(request.page_context["platform"])
        rule_config = agent_rule_store.get_rules(merchant_id=merchant_id, platform=platform)
        workflow_result = await default_workflow.run(
            merchant_id=merchant_id,
            user_query=user_query,
            conversation_history=workflow_history,
            page_context=request.page_context,
            rule_config=rule_config,
        )

        conversation_data = storage_manager.get_conversation(conversation_id)
        if conversation_data:
            conversation_data["last_intent"] = workflow_result.intent
            storage_manager.save_conversation(conversation_id, conversation_data)
            storage_manager.update_conversation_metadata(conversation_id, {"last_intent": workflow_result.intent})

        response = ChatResponse(
            **workflow_result.to_chat_response_payload(conversation_id=conversation_id),
            timestamp=datetime.now(),
        )
        _add_message_to_conversation(
            conversation_id,
            "assistant",
            response.response_text,
            metadata=_workflow_message_metadata(workflow_result, source="chat"),
        )
        return response
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in chat_query: %s", exc)
        raise HTTPException(status_code=500, detail=f"聊天处理失败: {exc}")


@router.post("/rpa/message", response_model=RpaMessageResponse)
async def rpa_message(request: RpaMessageRequest) -> RpaMessageResponse:
    """Stable RPA entrypoint.

    RPA tools should send one scraped buyer message to this endpoint and then
    only use decision.auto_send_allowed to decide whether to submit the reply.
    """

    try:
        merchant_id = request.merchant_id or "default"
        customer_message = request.customer_message.strip()
        if not customer_message:
            raise HTTPException(status_code=400, detail="customer_message cannot be empty")

        conversation_id = _get_or_create_rpa_conversation(
            merchant_id=merchant_id,
            platform=request.platform,
            external_conversation_id=request.external_conversation_id,
            customer_id=request.customer_id,
            customer_name=request.customer_name,
        )
        conversation_data = storage_manager.get_conversation(conversation_id) or {}
        processed_events = conversation_data.get("rpa_processed_events") or {}
        if request.external_message_id and request.external_message_id in processed_events:
            payload = processed_events[request.external_message_id]
            payload["message"]["duplicate_event"] = True
            return RpaMessageResponse(**payload)

        request_id = str(uuid.uuid4())
        _add_message_to_conversation(
            conversation_id,
            "user",
            customer_message,
            metadata={
                "source": "rpa",
                "platform": request.platform,
                "external_conversation_id": request.external_conversation_id,
                "external_message_id": request.external_message_id,
                "customer_id": request.customer_id,
                "customer_name": request.customer_name,
            },
        )

        workflow_history = _get_conversation_history(conversation_id, limit=10)
        page_context = request.page_context.model_dump(exclude_none=True) if request.page_context else None
        rule_config = agent_rule_store.get_rules(merchant_id=merchant_id, platform=request.platform)
        workflow_result = await default_workflow.run(
            merchant_id=merchant_id,
            user_query=customer_message,
            conversation_history=workflow_history,
            page_context=page_context,
            rule_config=rule_config,
        )

        conversation_data = storage_manager.get_conversation(conversation_id)
        if conversation_data:
            conversation_data["last_intent"] = workflow_result.intent
            conversation_data["last_rpa_decision"] = {
                "auto_send_allowed": workflow_result.auto_send_allowed,
                "risk_level": workflow_result.risk_level,
                "confidence": workflow_result.confidence,
                "auto_send_blockers": workflow_result.auto_send_blockers,
                "processed_at": datetime.now().isoformat(),
            }
            storage_manager.save_conversation(conversation_id, conversation_data)
            storage_manager.update_conversation_metadata(
                conversation_id,
                {
                    "last_intent": workflow_result.intent,
                    "last_updated": conversation_data.get("last_updated"),
                },
            )

        response_payload = _build_rpa_response_payload(
            request_id=request_id,
            request=request,
            conversation_id=conversation_id,
            workflow_result=workflow_result,
        )
        _add_message_to_conversation(
            conversation_id,
            "assistant",
            workflow_result.response_text,
            metadata=_workflow_message_metadata(
                workflow_result,
                source="rpa",
                request_id=request_id,
            ),
        )
        _remember_rpa_event(conversation_id, request.external_message_id, response_payload)

        # Create handoff ticket if the workflow says this needs human review
        if not workflow_result.auto_send_allowed or workflow_result.requires_human_review:
            try:
                handoff_store.create_ticket({
                    "merchant_id": merchant_id,
                    "platform": request.platform,
                    "conversation_id": conversation_id,
                    "external_conversation_id": request.external_conversation_id,
                    "external_message_id": request.external_message_id,
                    "customer_message": customer_message,
                    "recommended_reply": workflow_result.response_text or "",
                    "reason": workflow_result.handoff_reason or "blocked_by_policy",
                    "blockers": workflow_result.auto_send_blockers or [],
                    "risk_level": workflow_result.risk_level or "",
                    "confidence": workflow_result.confidence,
                    "source": "rpa_decision",
                })
            except Exception as ticket_err:
                logger.warning("Failed to create handoff ticket: %s", ticket_err)

        return RpaMessageResponse(**response_payload)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in rpa_message: %s", exc)
        raise HTTPException(status_code=500, detail=f"RPA 消息处理失败: {exc}")


@router.post("/rpa/send-result", response_model=RpaSendResultResponse)
async def rpa_send_result(request: RpaSendResultRequest) -> RpaSendResultResponse:
    """Record the real execution result reported by the Local Agent."""

    try:
        merchant_id = request.merchant_id or "default"
        conversation_id = _get_or_create_rpa_conversation(
            merchant_id=merchant_id,
            platform=request.platform,
            external_conversation_id=request.external_conversation_id,
        )
        record_payload = _json_ready(request.model_dump(exclude_none=True))
        record_payload["merchant_id"] = merchant_id
        record_payload["conversation_id"] = conversation_id
        record_payload["processing_status"] = _processing_status_from_send_status(request.send_status)
        send_result = rpa_runtime_store.save_send_result(record_payload)

        conversation_data = storage_manager.get_conversation(conversation_id) or {}
        conversation_data.update(
            {
                "last_updated": datetime.now().isoformat(),
                "last_send_status": request.send_status,
                "processing_status": record_payload["processing_status"],
                "last_send_result": send_result,
            }
        )
        storage_manager.save_conversation(conversation_id, conversation_data)
        storage_manager.update_conversation_metadata(
            conversation_id,
            {
                "last_updated": conversation_data["last_updated"],
                "status": conversation_data.get("status", "active"),
            },
        )

        if request.send_status == "success" and request.sent_text:
            _add_message_to_conversation(
                conversation_id,
                "assistant_sent",
                request.sent_text,
                metadata={
                    "source": "local_agent",
                    "request_id": request.request_id,
                    "send_status": request.send_status,
                    "agent_id": request.agent_id,
                    "external_message_id": request.external_message_id,
                },
            )

        # Sync handoff ticket based on send result
        try:
            if request.send_status == "handoff":
                handoff_store.create_ticket({
                    "merchant_id": merchant_id,
                    "platform": request.platform,
                    "conversation_id": conversation_id,
                    "external_conversation_id": request.external_conversation_id,
                    "external_message_id": request.external_message_id,
                    "customer_message": request.customer_message or "",
                    "recommended_reply": request.sent_text or "",
                    "reason": request.error_message or "send_result_handoff",
                    "source": "send_result",
                })
            elif request.send_status == "success":
                # If there's an active pending ticket for this message, resolve it
                existing_tickets = handoff_store.list_tickets(
                    merchant_id=merchant_id,
                    platform=request.platform,
                    status="pending",
                    limit=10,
                )
                for ticket in existing_tickets:
                    if (ticket.get("external_conversation_id") == request.external_conversation_id
                            and ticket.get("external_message_id") == request.external_message_id):
                        handoff_store.update_status(
                            ticket["ticket_id"], "resolved",
                            human_reply=request.sent_text or "",
                        )
                        break
        except Exception as ticket_err:
            logger.warning("Failed to sync handoff ticket in send-result: %s", ticket_err)

        return RpaSendResultResponse(
            conversation_id=conversation_id,
            send_result=send_result,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in rpa_send_result: %s", exc)
        raise HTTPException(status_code=500, detail=f"RPA 发送结果记录失败: {exc}")


@router.get("/rpa/send-results")
async def list_rpa_send_results(
    merchant_id: Optional[str] = None,
    platform: Optional[str] = None,
    external_conversation_id: Optional[str] = None,
    limit: int = 50,
) -> Dict[str, Any]:
    results = rpa_runtime_store.list_send_results(
        merchant_id=merchant_id,
        platform=platform,
        external_conversation_id=external_conversation_id,
        limit=limit,
    )
    return {
        "total": len(results),
        "send_results": results,
    }


@router.post("/webhook/{platform}")
async def chat_webhook(platform: str, request: Request) -> Dict[str, Any]:
    """Delegate platform webhooks to the chat manager."""

    try:
        payload = await request.json()
        headers = dict(request.headers)
        result = await chat_manager.process_webhook_event(platform, payload, headers)
        return {"status": "ok", "platform": platform, "result": result}
    except Exception as exc:
        logger.exception("Error processing webhook for platform=%s: %s", platform, exc)
        raise HTTPException(status_code=500, detail=f"webhook 处理失败: {exc}")


@router.get("/conversations/{conversation_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    conversation_id: str,
    limit: int = 10,
    offset: int = 0,
) -> ConversationHistoryResponse:
    try:
        conversation_data = storage_manager.get_conversation(conversation_id)
        if not conversation_data:
            raise HTTPException(status_code=404, detail=f"会话 {conversation_id} 不存在")

        messages = storage_manager.get_messages(conversation_id, limit, offset)
        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            merchant_id=conversation_data.get("merchant_id"),
            messages=messages,
            total_count=conversation_data.get("message_count", 0),
            returned_count=len(messages),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in get_conversation_history: %s", exc)
        raise HTTPException(status_code=500, detail=f"获取历史失败: {exc}")


@router.get("/conversations/{conversation_id}")
async def get_conversation_info(conversation_id: str) -> Dict[str, Any]:
    try:
        conversation_data = storage_manager.get_conversation(conversation_id)
        if not conversation_data:
            raise HTTPException(status_code=404, detail=f"会话 {conversation_id} 不存在")

        return {
            "conversation_id": conversation_id,
            "merchant_id": conversation_data.get("merchant_id"),
            "message_count": conversation_data.get("message_count", 0),
            "created_at": conversation_data.get("created_at"),
            "last_updated": conversation_data.get("last_updated"),
            "last_intent": conversation_data.get("last_intent"),
            "status": conversation_data.get("status", "active"),
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in get_conversation_info: %s", exc)
        raise HTTPException(status_code=500, detail=f"获取会话信息失败: {exc}")


@router.post("/conversations/{conversation_id}/close")
async def close_conversation(conversation_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
    try:
        conversation_data = storage_manager.get_conversation(conversation_id)
        if not conversation_data:
            raise HTTPException(status_code=404, detail=f"会话 {conversation_id} 不存在")

        conversation_data["status"] = "closed"
        conversation_data["last_updated"] = datetime.now().isoformat()
        if reason:
            conversation_data["close_reason"] = reason

        storage_manager.save_conversation(conversation_id, conversation_data)
        storage_manager.update_conversation_metadata(
            conversation_id,
            {
                "status": "closed",
                "last_updated": conversation_data["last_updated"],
            },
        )

        return {
            "conversation_id": conversation_id,
            "status": "closed",
            "message": "会话已关闭",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Error in close_conversation: %s", exc)
        raise HTTPException(status_code=500, detail=f"关闭会话失败: {exc}")


@router.get("/conversations")
async def list_conversations(merchant_id: Optional[str] = None) -> Dict[str, Any]:
    try:
        conversation_ids = storage_manager.list_conversations(merchant_id)
        conversations = []
        for conversation_id in conversation_ids:
            conversation_data = storage_manager.get_conversation(conversation_id)
            if conversation_data:
                conversations.append(
                    {
                        "conversation_id": conversation_id,
                        "merchant_id": conversation_data.get("merchant_id"),
                        "message_count": conversation_data.get("message_count", 0),
                        "created_at": conversation_data.get("created_at"),
                        "last_updated": conversation_data.get("last_updated"),
                        "last_intent": conversation_data.get("last_intent"),
                        "status": conversation_data.get("status", "active"),
                        "platform": conversation_data.get("platform"),
                        "customer_id": conversation_data.get("customer_id"),
                        "customer_name": conversation_data.get("customer_name"),
                        "external_conversation_id": conversation_data.get("rpa_external_conversation_id"),
                        "last_send_status": conversation_data.get("last_send_status"),
                        "processing_status": conversation_data.get("processing_status"),
                    }
                )

        return {
            "total": len(conversations),
            "conversations": conversations,
        }
    except Exception as exc:
        logger.exception("Error in list_conversations: %s", exc)
        raise HTTPException(status_code=500, detail=f"会话列表查询失败: {exc}")


@router.get("/health")
async def chat_health() -> Dict[str, Any]:
    try:
        stats = storage_manager.get_stats()
        conversation_ids = storage_manager.list_conversations()
        active_conversations = 0
        for conversation_id in conversation_ids:
            conversation_data = storage_manager.get_conversation(conversation_id)
            if conversation_data and conversation_data.get("status") == "active":
                active_conversations += 1

        return {
            "status": "healthy",
            "module": "chat",
            "active_conversations": active_conversations,
            "total_conversations": len(conversation_ids),
            "storage": stats,
        }
    except Exception as exc:
        logger.exception("Error in chat_health: %s", exc)
        return {
            "status": "unhealthy",
            "module": "chat",
            "error": str(exc),
        }
