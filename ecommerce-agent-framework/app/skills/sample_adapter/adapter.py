# sample adapter template
# 实现 ChatAdapter 协议的最小示例，作为 skill 模板

from typing import Dict, Any
from app.connectors.chat_base import ChatAdapter, ChatMessage

class SampleAdapter(ChatAdapter):
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    async def send_message(self, recipient_id: str, message: str) -> bool:
        # TODO: 调用平台发送消息的实现
        return True

    async def fetch_history(self, recipient_id: str, limit: int = 20):
        # TODO: 拉取平台会话历史
        return []

    async def close(self):
        # 清理连接/会话
        pass
