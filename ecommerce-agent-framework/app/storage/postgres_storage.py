# storage/postgres_storage.py
"""
PostgreSQL 存储适配器
负责摄取任务数据的持久化存储
"""

from typing import Dict, List, Optional, Any
from sqlalchemy import create_engine, Column
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
import logging
from datetime import datetime

from app.config import settings
from app.models.database import Base, IngestionTask, Conversation, Merchant

logger = logging.getLogger(__name__)


class PostgresStorage:
    """PostgreSQL 存储适配器"""

    def __init__(self):
        self.engine = None
        self.SessionLocal = None
        self._connect()

    def _connect(self):
        """连接到PostgreSQL"""
        try:
            database_url = f"postgresql://{settings.postgres_user}:{settings.postgres_password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
            self.engine = create_engine(database_url, echo=False)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

            # 创建表
            Base.metadata.create_all(bind=self.engine)

            # 测试连接
            with self.SessionLocal() as session:
                session.execute(text("SELECT 1"))

            logger.info(f"Connected to PostgreSQL at {settings.postgres_host}:{settings.postgres_port}")
        except Exception as e:
            logger.warning(f"Failed to connect to PostgreSQL: {e}. Using memory fallback.")
            self.engine = None

    def _get_session(self) -> Session:
        """获取数据库会话"""
        if not self.SessionLocal:
            raise Exception("Database not connected")
        return self.SessionLocal()

    # === 摄取任务管理 ===

    def save_ingestion_task(self, task_data: Dict[str, Any]) -> bool:
        """保存摄取任务"""
        if not self.engine:
            return False

        try:
            with self._get_session() as session:
                task = IngestionTask(
                    id=task_data["upload_id"],
                    merchant_id=task_data["merchant_id"],
                    status=task_data.get("status", "pending"),
                    files_received=task_data.get("files_received", 0),
                    documents_processed=task_data.get("documents_processed", 0),
                    chunks_created=task_data.get("chunks_created", 0),
                    vector_store_size=task_data.get("vector_store_size", 0),
                    progress_percentage=task_data.get("progress_percentage", 0.0),
                    error_message=task_data.get("error_message"),
                    files=task_data.get("files", [])
                )
                session.merge(task)  # 使用merge处理插入或更新
                session.commit()
                logger.debug(f"Saved ingestion task {task_data['upload_id']} to PostgreSQL")
                return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to save ingestion task {task_data.get('upload_id')}: {e}")
            return False

    def get_ingestion_task(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """获取摄取任务"""
        if not self.engine:
            return None

        try:
            with self._get_session() as session:
                task = session.query(IngestionTask).filter(IngestionTask.id == upload_id).first()
                return task.to_dict() if task else None
        except SQLAlchemyError as e:
            logger.error(f"Failed to get ingestion task {upload_id}: {e}")
            return None

    def update_ingestion_task(self, upload_id: str, updates: Dict[str, Any]) -> bool:
        """更新摄取任务"""
        if not self.engine:
            return False

        try:
            with self._get_session() as session:
                task = session.query(IngestionTask).filter(IngestionTask.id == upload_id).first()
                if task:
                    for key, value in updates.items():
                        if hasattr(task, key):
                            setattr(task, key, value)
                    task.updated_at = datetime.utcnow()
                    session.commit()
                    logger.debug(f"Updated ingestion task {upload_id}")
                    return True
                return False
        except SQLAlchemyError as e:
            logger.error(f"Failed to update ingestion task {upload_id}: {e}")
            return False

    def list_ingestion_tasks(self, merchant_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """列出摄取任务"""
        if not self.engine:
            return []

        try:
            with self._get_session() as session:
                query = session.query(IngestionTask)
                if merchant_id:
                    query = query.filter(IngestionTask.merchant_id == merchant_id)
                tasks = query.order_by(IngestionTask.created_at.desc()).limit(limit).all()
                return [task.to_dict() for task in tasks]
        except SQLAlchemyError as e:
            logger.error(f"Failed to list ingestion tasks: {e}")
            return []

    def delete_ingestion_task(self, upload_id: str) -> bool:
        """删除摄取任务"""
        if not self.engine:
            return False

        try:
            with self._get_session() as session:
                task = session.query(IngestionTask).filter(IngestionTask.id == upload_id).first()
                if task:
                    session.delete(task)
                    session.commit()
                    logger.debug(f"Deleted ingestion task {upload_id}")
                    return True
                return False
        except SQLAlchemyError as e:
            logger.error(f"Failed to delete ingestion task {upload_id}: {e}")
            return False

    # === 会话管理（元数据） ===

    def save_conversation_metadata(self, conversation_data: Dict[str, Any]) -> bool:
        """保存会话元数据"""
        if not self.engine:
            return False

        try:
            with self._get_session() as session:
                conv = Conversation(
                    id=conversation_data["conversation_id"],
                    merchant_id=conversation_data["merchant_id"],
                    last_intent=conversation_data.get("last_intent"),
                    status=conversation_data.get("status", "active"),
                    message_count=conversation_data.get("message_count", 0)
                )
                session.merge(conv)
                session.commit()
                logger.debug(f"Saved conversation metadata {conversation_data['conversation_id']}")
                return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to save conversation metadata {conversation_data.get('conversation_id')}: {e}")
            return False

    def get_conversation_metadata(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """获取会话元数据"""
        if not self.engine:
            return None

        try:
            with self._get_session() as session:
                conv = session.query(Conversation).filter(Conversation.id == conversation_id).first()
                return conv.to_dict() if conv else None
        except SQLAlchemyError as e:
            logger.error(f"Failed to get conversation metadata {conversation_id}: {e}")
            return None

    def update_conversation_metadata(self, conversation_id: str, updates: Dict[str, Any]) -> bool:
        """更新会话元数据"""
        if not self.engine:
            return False

        try:
            with self._get_session() as session:
                conv = session.query(Conversation).filter(Conversation.id == conversation_id).first()
                if conv:
                    for key, value in updates.items():
                        if hasattr(conv, key):
                            setattr(conv, key, value)
                    conv.last_updated = datetime.utcnow()
                    session.commit()
                    logger.debug(f"Updated conversation metadata {conversation_id}")
                    return True
                return False
        except SQLAlchemyError as e:
            logger.error(f"Failed to update conversation metadata {conversation_id}: {e}")
            return False

    def list_conversations_metadata(self, merchant_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """列出会话元数据"""
        if not self.engine:
            return []

        try:
            with self._get_session() as session:
                query = session.query(Conversation)
                if merchant_id:
                    query = query.filter(Conversation.merchant_id == merchant_id)
                convs = query.order_by(Conversation.last_updated.desc()).limit(limit).all()
                return [conv.to_dict() for conv in convs]
        except SQLAlchemyError as e:
            logger.error(f"Failed to list conversations metadata: {e}")
            return []

    # === 商家管理 ===

    def save_merchant(self, merchant_data: Dict[str, Any]) -> bool:
        """保存商家信息"""
        if not self.engine:
            return False

        try:
            with self._get_session() as session:
                merchant = Merchant(
                    id=merchant_data["merchant_id"],
                    name=merchant_data.get("name"),
                    platform=merchant_data.get("platform"),
                    api_config=merchant_data.get("api_config")
                )
                session.merge(merchant)
                session.commit()
                logger.debug(f"Saved merchant {merchant_data['merchant_id']}")
                return True
        except SQLAlchemyError as e:
            logger.error(f"Failed to save merchant {merchant_data.get('merchant_id')}: {e}")
            return False

    def get_merchant(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        """获取商家信息"""
        if not self.engine:
            return None

        try:
            with self._get_session() as session:
                merchant = session.query(Merchant).filter(Merchant.id == merchant_id).first()
                return merchant.to_dict() if merchant else None
        except SQLAlchemyError as e:
            logger.error(f"Failed to get merchant {merchant_id}: {e}")
            return None

    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        if not self.engine:
            return {"status": "disconnected"}

        try:
            with self._get_session() as session:
                ingestion_count = session.query(IngestionTask).count()
                conversation_count = session.query(Conversation).count()
                merchant_count = session.query(Merchant).count()

                return {
                    "status": "connected",
                    "ingestion_tasks": ingestion_count,
                    "conversations": conversation_count,
                    "merchants": merchant_count
                }
        except SQLAlchemyError as e:
            return {"status": "error", "error": str(e)}


# 全局PostgreSQL存储实例
postgres_storage = PostgresStorage()