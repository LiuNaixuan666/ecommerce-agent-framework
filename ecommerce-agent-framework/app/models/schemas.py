"""
Pydantic Schemas for API Request/Response Models

This module defines all data models used in the API layer, including:
- Chat API models
- Knowledge management models
- Conversation management models
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ==================== Chat API Models ====================

class ConversationMessage(BaseModel):
    """单条会话消息"""
    role: str = Field(..., description="消息角色: 'user' 或 'assistant'")
    content: str = Field(..., description="消息内容")
    timestamp: Optional[datetime] = Field(default_factory=datetime.now, description="消息时间戳")
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="消息元数据，包括检索证据与发送状态",
    )


class ChatRequest(BaseModel):
    """聊天请求（单轮）"""
    merchant_id: str = Field(..., description="商家 ID")
    user_query: str = Field(..., description="用户查询")
    conversation_history: Optional[List[ConversationMessage]] = Field(
        default=None, 
        description="会话历史（用于多轮对话）"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="会话 ID（如果为 None，则创建新会话）"
    )


class ChatResponse(BaseModel):
    """聊天响应"""
    merchant_id: str = Field(..., description="商家 ID")
    user_query: str = Field(..., description="用户原始查询")
    response_text: str = Field(..., description="系统回答")
    intent: Optional[str] = Field(default=None, description="识别的意图类型")
    confidence: Optional[float] = Field(default=None, description="回答置信度 (0-1)")
    sources: Optional[List[str]] = Field(default=None, description="回答信息源列表")
    is_clarification_triggered: bool = Field(
        default=False, 
        description="是否触发了澄清流程"
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="会话 ID（用于后续追踪）"
    )
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间戳")


# ==================== Knowledge Management Models ====================

class KnowledgeUploadRequest(BaseModel):
    """文档上传请求"""
    merchant_id: str = Field(..., description="商家 ID")


class KnowledgeUploadResponse(BaseModel):
    """文档上传响应"""
    merchant_id: str = Field(..., description="商家 ID")
    status: str = Field(..., description="上传状态: 'pending', 'processing', 'completed', 'failed'")
    files_received: int = Field(default=0, description="接收到的文件数")
    upload_id: str = Field(..., description="上传任务 ID")
    message: str = Field(..., description="状态消息")
    timestamp: datetime = Field(default_factory=datetime.now, description="上传时间戳")


class IngestionStatusResponse(BaseModel):
    """摄取状态查询响应"""
    merchant_id: str = Field(..., description="商家 ID")
    upload_id: str = Field(..., description="上传任务 ID")
    status: str = Field(..., description="摄取状态: 'pending', 'processing', 'completed', 'failed'")
    documents_processed: int = Field(default=0, description="已处理文档数")
    chunks_created: int = Field(default=0, description="已创建文本块数")
    vector_store_size: int = Field(default=0, description="向量库大小")
    progress_percentage: int = Field(default=0, description="进度百分比 (0-100)")
    error_message: Optional[str] = Field(default=None, description="错误信息（如果有）")
    timestamp: datetime = Field(default_factory=datetime.now, description="查询时间戳")
    estimated_time_remaining: Optional[int] = Field(
        default=None, 
        description="预计剩余时间（秒）"
    )


class IngestionStartRequest(BaseModel):
    """触发摄取请求"""
    merchant_id: str = Field(..., description="商家 ID")
    upload_id: str = Field(..., description="上传任务 ID")


class IngestionStartResponse(BaseModel):
    """触发摄取响应"""
    merchant_id: str = Field(..., description="商家 ID")
    upload_id: str = Field(..., description="上传任务 ID")
    status: str = Field(..., description="摄取开始状态")
    message: str = Field(..., description="状态消息")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间戳")


# ==================== Conversation Management Models ====================

class ConversationSummary(BaseModel):
    """会话摘要"""
    conversation_id: str = Field(..., description="会话 ID")
    merchant_id: str = Field(..., description="商家 ID")
    message_count: int = Field(default=0, description="消息总数")
    created_at: datetime = Field(..., description="创建时间")
    last_updated: datetime = Field(..., description="最后更新时间")
    last_intent: Optional[str] = Field(default=None, description="最后一条消息的意图")
    status: str = Field(default="active", description="会话状态: 'active', 'archived', 'closed'")


class ConversationHistoryRequest(BaseModel):
    """会话历史查询请求"""
    conversation_id: str = Field(..., description="会话 ID")
    limit: int = Field(default=10, description="返回消息数上限")
    offset: int = Field(default=0, description="偏移量")


class ConversationHistoryResponse(BaseModel):
    """会话历史响应"""
    conversation_id: str = Field(..., description="会话 ID")
    merchant_id: str = Field(..., description="商家 ID")
    messages: List[ConversationMessage] = Field(..., description="消息列表")
    total_count: int = Field(..., description="消息总数")
    returned_count: int = Field(..., description="本次返回消息数")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间戳")


class ConversationCloseRequest(BaseModel):
    """关闭会话请求"""
    conversation_id: str = Field(..., description="会话 ID")
    reason: Optional[str] = Field(default=None, description="关闭原因")


class ConversationCloseResponse(BaseModel):
    """关闭会话响应"""
    conversation_id: str = Field(..., description="会话 ID")
    status: str = Field(..., description="关闭状态")
    message: str = Field(..., description="状态消息")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间戳")


# ==================== Health Check Models ====================

class HealthCheckResponse(BaseModel):
    """系统健康状态响应"""
    status: str = Field(..., description="系统状态: 'healthy', 'initializing', 'degraded'")
    components: Dict[str, str] = Field(..., description="各组件状态")
    timestamp: datetime = Field(default_factory=datetime.now, description="检查时间戳")
    message: Optional[str] = Field(default=None, description="状态消息")


# ==================== Intent & Entity Models ====================

class IntentSchema(BaseModel):
    """意图识别结果"""
    intent_label: str = Field(..., description="意图标签")
    detected_entities: List[str] = Field(default_factory=list, description="检测到的实体")
    confidence_score: float = Field(..., description="置信度 (0-1)")
    reasoning: Optional[str] = Field(default=None, description="推理过程")


class UncertaintyResult(BaseModel):
    """不确定性检测结果"""
    confidence_score: float = Field(..., description="综合置信度")
    is_uncertain: bool = Field(..., description="是否不确定")
    recommendation: str = Field(..., description="建议")
    details: Dict[str, Any] = Field(default_factory=dict, description="详细信息")


# ==================== Error Models ====================

class ErrorResponse(BaseModel):
    """错误响应"""
    error_code: str = Field(..., description="错误代码")
    error_message: str = Field(..., description="错误信息")
    details: Optional[Dict[str, Any]] = Field(default=None, description="详细信息")
    timestamp: datetime = Field(default_factory=datetime.now, description="错误时间戳")
