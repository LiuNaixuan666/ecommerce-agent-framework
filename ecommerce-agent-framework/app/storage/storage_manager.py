# storage/storage_manager.py
"""
存储管理器
统一管理不同存储后端的访问，提供统一的接口
"""

from typing import Dict, List, Optional, Any
from app.config import settings
from app.storage.redis_storage import redis_storage
from app.storage.postgres_storage import postgres_storage
import logging

logger = logging.getLogger(__name__)


class StorageManager:
    """统一存储管理器"""

    def __init__(self):
        self.session_backend = self._get_session_backend()
        self.ingestion_backend = self._get_ingestion_backend()
        logger.info(f"StorageManager initialized: session={self.session_backend.__class__.__name__}, ingestion={self.ingestion_backend.__class__.__name__}")

    def _get_session_backend(self):
        """获取会话存储后端"""
        if settings.session_storage == "redis" and redis_storage.client:
            return redis_storage
        else:
            # 默认使用内存存储
            return MemorySessionStorage()

    def _get_ingestion_backend(self):
        """获取摄取任务存储后端"""
        if settings.ingestion_storage == "postgres" and postgres_storage.engine:
            return postgres_storage
        else:
            # 默认使用内存存储
            return MemoryIngestionStorage()

    # === 会话管理 ===

    def save_conversation(self, conversation_id: str, data: Dict[str, Any]) -> bool:
        """保存会话数据"""
        return self.session_backend.save_conversation(conversation_id, data)

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """获取会话数据"""
        return self.session_backend.get_conversation(conversation_id)

    def delete_conversation(self, conversation_id: str) -> bool:
        """删除会话数据"""
        return self.session_backend.delete_conversation(conversation_id)

    def save_messages(self, conversation_id: str, messages: List[Dict[str, Any]]) -> bool:
        """保存会话消息历史"""
        return self.session_backend.save_messages(conversation_id, messages)

    def get_messages(self, conversation_id: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """获取会话消息历史"""
        return self.session_backend.get_messages(conversation_id, limit, offset)

    def add_message(self, conversation_id: str, message: Dict[str, Any]) -> bool:
        """添加单条消息到会话"""
        return self.session_backend.add_message(conversation_id, message)

    def list_conversations(self, merchant_id: Optional[str] = None, limit: int = 50) -> List[str]:
        """列出会话ID"""
        return self.session_backend.list_conversations(merchant_id, limit)

    # === 摄取任务管理 ===

    def save_ingestion_task(self, task_data: Dict[str, Any]) -> bool:
        """保存摄取任务"""
        return self.ingestion_backend.save_ingestion_task(task_data)

    def get_ingestion_task(self, upload_id: str) -> Optional[Dict[str, Any]]:
        """获取摄取任务"""
        return self.ingestion_backend.get_ingestion_task(upload_id)

    def update_ingestion_task(self, upload_id: str, updates: Dict[str, Any]) -> bool:
        """更新摄取任务"""
        return self.ingestion_backend.update_ingestion_task(upload_id, updates)

    def list_ingestion_tasks(self, merchant_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """列出摄取任务"""
        return self.ingestion_backend.list_ingestion_tasks(merchant_id, limit)

    def delete_ingestion_task(self, upload_id: str) -> bool:
        """删除摄取任务"""
        return self.ingestion_backend.delete_ingestion_task(upload_id)

    # === 会话元数据管理（PostgreSQL） ===

    def save_conversation_metadata(self, conversation_data: Dict[str, Any]) -> bool:
        """保存会话元数据"""
        if hasattr(self.ingestion_backend, 'save_conversation_metadata'):
            return self.ingestion_backend.save_conversation_metadata(conversation_data)
        return False

    def get_conversation_metadata(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """获取会话元数据"""
        if hasattr(self.ingestion_backend, 'get_conversation_metadata'):
            return self.ingestion_backend.get_conversation_metadata(conversation_id)
        return None

    def update_conversation_metadata(self, conversation_id: str, updates: Dict[str, Any]) -> bool:
        """更新会话元数据"""
        if hasattr(self.ingestion_backend, 'update_conversation_metadata'):
            return self.ingestion_backend.update_conversation_metadata(conversation_id, updates)
        return False

    def list_conversations_metadata(self, merchant_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """列出会话元数据"""
        if hasattr(self.ingestion_backend, 'list_conversations_metadata'):
            return self.ingestion_backend.list_conversations_metadata(merchant_id, limit)
        return []

    # === 商家管理 ===

    def save_merchant(self, merchant_data: Dict[str, Any]) -> bool:
        """保存商家信息"""
        if hasattr(self.ingestion_backend, 'save_merchant'):
            return self.ingestion_backend.save_merchant(merchant_data)
        return False

    def get_merchant(self, merchant_id: str) -> Optional[Dict[str, Any]]:
        """获取商家信息"""
        if hasattr(self.ingestion_backend, 'get_merchant'):
            return self.ingestion_backend.get_merchant(merchant_id)
        return None

    # === 统计信息 ===

    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        session_stats = self.session_backend.get_stats() if hasattr(self.session_backend, 'get_stats') else {"status": "unknown"}
        ingestion_stats = self.ingestion_backend.get_stats() if hasattr(self.ingestion_backend, 'get_stats') else {"status": "unknown"}

        return {
            "session_storage": session_stats,
            "ingestion_storage": ingestion_stats,
            "config": {
                "session_backend": settings.session_storage,
                "ingestion_backend": settings.ingestion_storage
            }
        }


class MemorySessionStorage:
    """内存会话存储（后备方案）"""

    def __init__(self):
        self.conversations = {}
        self.messages = {}

    def save_conversation(self, conversation_id: str, data: Dict[str, Any]) -> bool:
        self.conversations[conversation_id] = data
        return True

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        return self.conversations.get(conversation_id)

    def delete_conversation(self, conversation_id: str) -> bool:
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            if conversation_id in self.messages:
                del self.messages[conversation_id]
            return True
        return False

    def save_messages(self, conversation_id: str, messages: List[Dict[str, Any]]) -> bool:
        self.messages[conversation_id] = messages
        return True

    def get_messages(self, conversation_id: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        messages = self.messages.get(conversation_id, [])
        start = max(0, len(messages) - offset - limit)
        end = max(0, len(messages) - offset)
        return messages[start:end]

    def add_message(self, conversation_id: str, message: Dict[str, Any]) -> bool:
        if conversation_id not in self.messages:
            self.messages[conversation_id] = []
        self.messages[conversation_id].append(message)
        return True

    def list_conversations(self, merchant_id: Optional[str] = None, limit: int = 50) -> List[str]:
        conv_ids = list(self.conversations.keys())
        if merchant_id:
            conv_ids = [cid for cid in conv_ids if self.conversations[cid].get("merchant_id") == merchant_id]
        return conv_ids[-limit:] if len(conv_ids) > limit else conv_ids

    def get_stats(self) -> Dict[str, Any]:
        return {
            "status": "memory",
            "total_conversations": len(self.conversations),
            "total_messages": sum(len(msgs) for msgs in self.messages.values())
        }


class MemoryIngestionStorage:
    """内存摄取任务存储（后备方案）"""

    def __init__(self):
        self.tasks = {}

    def save_ingestion_task(self, task_data: Dict[str, Any]) -> bool:
        self.tasks[task_data["upload_id"]] = task_data.copy()
        return True

    def get_ingestion_task(self, upload_id: str) -> Optional[Dict[str, Any]]:
        return self.tasks.get(upload_id)

    def update_ingestion_task(self, upload_id: str, updates: Dict[str, Any]) -> bool:
        if upload_id in self.tasks:
            self.tasks[upload_id].update(updates)
            return True
        return False

    def list_ingestion_tasks(self, merchant_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        tasks = list(self.tasks.values())
        if merchant_id:
            tasks = [t for t in tasks if t.get("merchant_id") == merchant_id]
        return tasks[-limit:] if len(tasks) > limit else tasks

    def delete_ingestion_task(self, upload_id: str) -> bool:
        if upload_id in self.tasks:
            del self.tasks[upload_id]
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "status": "memory",
            "total_tasks": len(self.tasks)
        }


# 全局存储管理器实例
storage_manager = StorageManager()