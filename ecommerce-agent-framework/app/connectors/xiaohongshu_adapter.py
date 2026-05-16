# app/connectors/xiaohongshu_adapter.py
"""
Xiaohongshu (小红书) Chat Adapter

Implementation for Xiaohongshu e-commerce chat integration.
Based on Xiaohongshu Open Platform APIs.
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime, timedelta
import aiohttp
from urllib.parse import urlencode

from .chat_base import ChatAdapter, ChatMessage, Conversation, ChatAdapterFactory

logger = logging.getLogger(__name__)


class XiaohongshuChatAdapter(ChatAdapter):
    """Xiaohongshu chat adapter implementation"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.app_id = config.get('app_id', '')
        self.app_secret = config.get('app_secret', '')
        self.webhook_token = config.get('webhook_token', '')
        self.api_base_url = config.get('api_base_url', 'https://api.xiaohongshu.com')
        self.merchant_id = config.get('merchant_id', '')

        self._session: Optional[aiohttp.ClientSession] = None
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    @property
    def platform_name(self) -> str:
        return 'xiaohongshu'

    async def initialize(self, config: Dict[str, Any]) -> bool:
        """Initialize the adapter"""
        try:
            self.config.update(config)
            self._session = aiohttp.ClientSession(
                headers={
                    'Content-Type': 'application/json',
                    'User-Agent': 'EcommerceAgent/1.0'
                }
            )

            # Get access token
            await self._refresh_access_token()

            logger.info("Xiaohongshu adapter initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Xiaohongshu adapter: {e}")
            return False

    async def _refresh_access_token(self) -> None:
        """Refresh access token"""
        try:
            # Note: This is a placeholder implementation
            # Actual implementation depends on Xiaohongshu's OAuth flow
            auth_url = f"{self.api_base_url}/oauth2/access_token"

            auth_data = {
                'grant_type': 'client_credentials',
                'client_id': self.app_id,
                'client_secret': self.app_secret
            }

            async with self._session.post(auth_url, json=auth_data) as response:
                if response.status == 200:
                    data = await response.json()
                    self._access_token = data.get('access_token')
                    expires_in = data.get('expires_in', 7200)  # Default 2 hours
                    self._token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                    logger.info("Access token refreshed successfully")
                else:
                    raise Exception(f"Failed to get access token: {response.status}")

        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}")
            raise

    async def _ensure_valid_token(self) -> None:
        """Ensure access token is valid"""
        if not self._access_token or \
           (self._token_expires_at and datetime.now() >= self._token_expires_at):
            await self._refresh_access_token()

    async def send_message(self, conversation_id: str, content: str, **kwargs) -> bool:
        """Send a message to a conversation"""
        try:
            await self._ensure_valid_token()

            # Get platform conversation ID
            platform_conv_id = await self._get_platform_conversation_id(conversation_id)

            send_url = f"{self.api_base_url}/v1/chat/send"

            message_data = {
                'conversation_id': platform_conv_id,
                'content': content,
                'content_type': 'text',
                'timestamp': datetime.now().isoformat()
            }

            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Content-Type': 'application/json'
            }

            async with self._session.post(send_url, json=message_data, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"Message sent successfully: {result.get('message_id')}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Failed to send message: {response.status} - {error_text}")
                    return False

        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False

    async def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[ChatMessage]:
        """Get conversation history"""
        try:
            await self._ensure_valid_token()

            platform_conv_id = await self._get_platform_conversation_id(conversation_id)

            history_url = f"{self.api_base_url}/v1/chat/history"
            params = {
                'conversation_id': platform_conv_id,
                'limit': limit
            }

            headers = {'Authorization': f'Bearer {self._access_token}'}

            async with self._session.get(history_url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    messages = []

                    for msg_data in data.get('messages', []):
                        message = ChatMessage(
                            message_id=msg_data['id'],
                            conversation_id=conversation_id,
                            platform_conversation_id=platform_conv_id,
                            sender_id=msg_data['sender_id'],
                            sender_type=msg_data['sender_type'],
                            content=msg_data['content'],
                            content_type=msg_data.get('content_type', 'text'),
                            timestamp=datetime.fromisoformat(msg_data['timestamp']),
                            metadata=msg_data.get('metadata', {})
                        )
                        messages.append(message)

                    return messages
                else:
                    logger.error(f"Failed to get conversation history: {response.status}")
                    return []

        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return []

    async def _get_platform_conversation_id(self, conversation_id: str) -> str:
        """Get platform conversation ID from our internal ID"""
        # This would typically involve a database lookup
        # For now, assume conversation_id is the platform ID
        return conversation_id

    async def mark_message_read(self, message_id: str) -> bool:
        """Mark a message as read"""
        try:
            await self._ensure_valid_token()

            read_url = f"{self.api_base_url}/v1/chat/mark_read"

            data = {'message_id': message_id}
            headers = {'Authorization': f'Bearer {self._access_token}'}

            async with self._session.post(read_url, json=data, headers=headers) as response:
                return response.status == 200

        except Exception as e:
            logger.error(f"Error marking message as read: {e}")
            return False

    async def get_active_conversations(self, merchant_id: str) -> List[Conversation]:
        """Get all active conversations for a merchant"""
        try:
            await self._ensure_valid_token()

            conv_url = f"{self.api_base_url}/v1/chat/conversations"
            params = {'merchant_id': merchant_id, 'status': 'active'}

            headers = {'Authorization': f'Bearer {self._access_token}'}

            async with self._session.get(conv_url, params=params, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    conversations = []

                    for conv_data in data.get('conversations', []):
                        conversation = Conversation(
                            conversation_id=conv_data['id'],  # Our internal ID
                            platform_conversation_id=conv_data['platform_id'],
                            merchant_id=merchant_id,
                            customer_id=conv_data['customer_id'],
                            platform=self.platform_name,
                            status=conv_data['status'],
                            created_at=datetime.fromisoformat(conv_data['created_at']),
                            last_updated=datetime.fromisoformat(conv_data['last_updated']),
                            message_count=conv_data.get('message_count', 0),
                            metadata=conv_data.get('metadata', {})
                        )
                        conversations.append(conversation)

                    return conversations
                else:
                    logger.error(f"Failed to get active conversations: {response.status}")
                    return []

        except Exception as e:
            logger.error(f"Error getting active conversations: {e}")
            return []

    async def close_conversation(self, conversation_id: str) -> bool:
        """Close a conversation"""
        try:
            await self._ensure_valid_token()

            platform_conv_id = await self._get_platform_conversation_id(conversation_id)

            close_url = f"{self.api_base_url}/v1/chat/close"

            data = {'conversation_id': platform_conv_id}
            headers = {'Authorization': f'Bearer {self._access_token}'}

            async with self._session.post(close_url, json=data, headers=headers) as response:
                return response.status == 200

        except Exception as e:
            logger.error(f"Error closing conversation: {e}")
            return False

    async def listen_for_messages(self) -> AsyncGenerator[ChatMessage, None]:
        """Listen for new incoming messages"""
        # This would typically be implemented as a webhook handler
        # For polling implementation:
        last_check = datetime.now()

        while True:
            try:
                await self._ensure_valid_token()

                poll_url = f"{self.api_base_url}/v1/chat/poll"
                params = {
                    'merchant_id': self.merchant_id,
                    'since': last_check.isoformat()
                }

                headers = {'Authorization': f'Bearer {self._access_token}'}

                async with self._session.get(poll_url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()

                        for msg_data in data.get('messages', []):
                            message = ChatMessage(
                                message_id=msg_data['id'],
                                conversation_id=msg_data['conversation_id'],  # Our internal ID
                                platform_conversation_id=msg_data['platform_conversation_id'],
                                sender_id=msg_data['sender_id'],
                                sender_type='user',  # Assuming incoming messages are from users
                                content=msg_data['content'],
                                content_type=msg_data.get('content_type', 'text'),
                                timestamp=datetime.fromisoformat(msg_data['timestamp']),
                                metadata=msg_data.get('metadata', {})
                            )
                            yield message

                        last_check = datetime.now()

                    else:
                        logger.warning(f"Failed to poll messages: {response.status}")

                await asyncio.sleep(5)  # Poll every 5 seconds

            except Exception as e:
                logger.error(f"Error polling messages: {e}")
                await asyncio.sleep(10)  # Wait longer on error

    async def validate_webhook(self, request_data: Dict[str, Any]) -> bool:
        """Validate incoming webhook requests"""
        # Implement webhook signature validation
        # This depends on Xiaohongshu's webhook security mechanism
        signature = request_data.get('signature', '')
        timestamp = request_data.get('timestamp', '')

        # Placeholder validation logic
        expected_signature = self._calculate_webhook_signature(timestamp)

        return signature == expected_signature

    def _calculate_webhook_signature(self, timestamp: str) -> str:
        """Calculate webhook signature"""
        # Implement actual signature calculation based on Xiaohongshu's docs
        import hmac
        import hashlib

        message = f"{timestamp}{self.webhook_token}"
        return hmac.new(
            self.webhook_token.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()

    async def get_platform_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get platform user information"""
        try:
            await self._ensure_valid_token()

            user_url = f"{self.api_base_url}/v1/user/{user_id}"

            headers = {'Authorization': f'Bearer {self._access_token}'}

            async with self._session.get(user_url, headers=headers) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    return None

        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    async def close(self):
        """Close the adapter and cleanup resources"""
        if self._session:
            await self._session.close()


# Register this adapter with the factory so ChatManager can load it dynamically.
ChatAdapterFactory.register('xiaohongshu', XiaohongshuChatAdapter)