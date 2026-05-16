# models/database.py
"""
数据库模型定义
使用 SQLAlchemy ORM 定义数据表结构
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

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
    """会话表（主要元数据，消息存储在Redis中）"""
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True)  # UUID
    merchant_id = Column(String(100), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_intent = Column(String(50), nullable=True)
    status = Column(String(20), default="active")  # active, closed
    message_count = Column(Integer, default=0)

    def to_dict(self):
        return {
            "conversation_id": self.id,
            "merchant_id": self.merchant_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
            "last_intent": self.last_intent,
            "status": self.status,
            "message_count": self.message_count
        }


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