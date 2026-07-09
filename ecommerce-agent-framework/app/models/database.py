# models/database.py
"""
数据库模型定义
使用 SQLAlchemy ORM 定义数据表结构
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey, Index
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class IngestionTask(Base):
    """摄取任务表"""
    __tablename__ = "ingestion_tasks"

    id = Column(String(36), primary_key=True)  # UUID
    merchant_id = Column(String(100), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="pending")  # pending, processing, completed, failed
    files_received = Column(Integer, default=0)
    documents_processed = Column(Integer, default=0)
    chunks_created = Column(Integer, default=0)
    vector_store_size = Column(Integer, default=0)
    progress_percentage = Column(Float, default=0.0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 文件列表（JSON格式存储）
    files = Column(JSON, default=list)

    def to_dict(self):
        return {
            "upload_id": self.id,
            "merchant_id": self.merchant_id,
            "status": self.status,
            "files_received": self.files_received,
            "documents_processed": self.documents_processed,
            "chunks_created": self.chunks_created,
            "vector_store_size": self.vector_store_size,
            "progress_percentage": self.progress_percentage,
            "error_message": self.error_message,
            "timestamp": self.updated_at.isoformat() if self.updated_at else None
        }


class Conversation(Base):
    """会话元数据及平台扩展状态。"""
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True)  # UUID
    merchant_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_intent = Column(String(50), nullable=True)
    status = Column(String(20), default="active")  # active, closed
    message_count = Column(Integer, default=0)
    extra_data = Column("metadata", JSON, default=dict)

    def to_dict(self):
        result = dict(self.extra_data or {})
        result.update({
            "conversation_id": self.id,
            "merchant_id": self.merchant_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "last_intent": self.last_intent,
            "status": self.status,
            "message_count": self.message_count
        })
        return result


class ConversationMessageRecord(Base):
    """永久保存的会话消息，包括 AI 检索证据。"""
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(
        String(36),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(30), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    message_metadata = Column("metadata", JSON, default=dict)

    __table_args__ = (
        Index("ix_conversation_messages_conversation_created", "conversation_id", "created_at"),
    )

    def to_dict(self):
        result = {
            "role": self.role,
            "content": self.content,
            "timestamp": self.created_at.isoformat() if self.created_at else None,
        }
        if self.message_metadata:
            result["metadata"] = self.message_metadata
        return result


class Merchant(Base):
    """商家信息表"""
    __tablename__ = "merchants"

    id = Column(String(100), primary_key=True)
    name = Column(String(200), nullable=True)
    platform = Column(String(50), nullable=True)  # taobao, jd, etc.
    api_config = Column(JSON, nullable=True)  # 平台API配置
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "merchant_id": self.id,
            "name": self.name,
            "platform": self.platform,
            "api_config": self.api_config,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
