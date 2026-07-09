# storage/redis_storage.py
"""
Redis 存储适配器
负责会话数据的持久化存储
"""

import json
import redis
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class RedisStorage:
    """Redis 存储适配器"""

    def __init__(self):
        self.client = None
        self._connect()

    def _connect(self):
        """连接到Redis"""
        try:
            self.client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                db=settings.redis_db,
                password=settings.redis_password,
                decode_responses=True
            )
            # 测试连接
            self.client.ping()
            logger.info(f"Connected to Redis at {settings.redis_host}:{settings.redis_port}")
        except redis.ConnectionError as e:
            logger.warning(f"Failed to connect to Redis: {e}. Using memory fallback.")
            self.client = None

    def _get_key(self, conversation_id: str, key: str = "") -> str:
        """生成Redis键"""
        base_key = f"conversation:{conversation_id}"
        return f"{base_key}:{key}" if key else base_key

    def save_conversation(self, conversation_id: str, data: Dict[str, Any]) -> bool:
        """保存会话数据"""
        if not self.client:
            return False

        try:
            key = self._get_key(conversation_id)
            # 设置过期时间
            self.client.setex(key, settings.redis_session_ttl, json.dumps(data))
            logger.debug(f"Saved conversation {conversation_id} to Redis")
            return True
        except Exception as e:
            logger.error(f"Failed to save conversation {conversation_id}: {e}")
            return False

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """获取会话数据"""
        if not self.client:
            return None

        try:
            key = self._get_key(conversation_id)
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Failed to get conversation {conversation_id}: {e}")
            return None

    def delete_conversation(self, conversation_id: str) -> bool:
        """删除会话数据"""
        if not self.client:
            return False

        try:
            conversation_key = self._get_key(conversation_id)
            messages_key = self._get_key(conversation_id, "messages")
            self.client.delete(conversation_key, messages_key)
            logger.debug(f"Deleted conversation {conversation_id} from Redis")
            return True
        except Exception as e:
            logger.error(f"Failed to delete conversation {conversation_id}: {e}")
            return False

    def save_messages(self, conversation_id: str, messages: List[Dict[str, Any]]) -> bool:
        """保存会话消息历史"""
        if not self.client:
            return False

        try:
            key = self._get_key(conversation_id, "messages")
            self.client.setex(key, settings.redis_session_ttl, json.dumps(messages))
            logger.debug(f"Saved {len(messages)} messages for conversation {conversation_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save messages for conversation {conversation_id}: {e}")
            return False

    def get_messages(self, conversation_id: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """获取会话消息历史"""
        if not self.client:
            return []

        try:
            key = self._get_key(conversation_id, "messages")
            data = self.client.get(key)
            if data:
                messages = json.loads(data)
                # 分页返回
                start = max(0, len(messages) - offset - limit)
                end = max(0, len(messages) - offset)
                return messages[start:end]
            return []
        except Exception as e:
            logger.error(f"Failed to get messages for conversation {conversation_id}: {e}")
            return []

    def add_message(self, conversation_id: str, message: Dict[str, Any]) -> bool:
        """添加单条消息到会话"""
        if not self.client:
            return False

        try:
            key = self._get_key(conversation_id, "messages")
            data = self.client.get(key)
            messages = json.loads(data) if data else []
            messages.append(message)

            # 限制消息数量（避免内存溢出）
            max_messages = 100
            if len(messages) > max_messages:
                messages = messages[-max_messages:]

            self.client.setex(key, settings.redis_session_ttl, json.dumps(messages))
            logger.debug(f"Added message to conversation {conversation_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add message to conversation {conversation_id}: {e}")
            return False

    def list_conversations(self, merchant_id: Optional[str] = None, limit: int = 50) -> List[str]:
        """列出所有会话ID"""
        if not self.client:
            return []

        try:
            keys = [
                key
                for key in self.client.scan_iter(match="conversation:*")
                if key.count(":") == 1
            ]
            conversation_ids = []

            for key in keys:
                # 过滤特定商家的会话
                if merchant_id:
                    data = self.client.get(key)
                    if data:
                        try:
                            conv_data = json.loads(data)
                            if conv_data.get("merchant_id") == merchant_id:
                                conv_id = key.split(":")[1]
                                conversation_ids.append(conv_id)
                        except:
                            continue
                else:
                    conv_id = key.split(":")[1]
                    conversation_ids.append(conv_id)

            # 按时间排序（最近的在前）
            return conversation_ids[-limit:] if len(conversation_ids) > limit else conversation_ids
        except Exception as e:
            logger.error(f"Failed to list conversations: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """获取存储统计信息"""
        if not self.client:
            return {"status": "disconnected"}

        try:
            info = self.client.info()
            keys = [
                key
                for key in self.client.scan_iter(match="conversation:*")
                if key.count(":") == 1
            ]
            return {
                "status": "connected",
                "total_conversations": len(keys),
                "memory_used": info.get("used_memory_human", "unknown"),
                "uptime": info.get("uptime_in_seconds", 0)
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# 全局Redis存储实例
redis_storage = RedisStorage()
