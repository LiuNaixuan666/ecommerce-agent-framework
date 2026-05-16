# app/connectors/chat_base.py
"""
Chat Adapter Interface for E-commerce Platforms

This module defines the interface for chat/message integration with various e-commerce platforms.
Supports real-time messaging, conversation management, and platform-specific features.
"""

from typing import Protocol, Dict, List, Optional, Any, AsyncGenerator
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ChatMessage:
    """Unified chat message structure"""
    message_id: str
    conversation_id: str
    platform_conversation_id: str  # Platform-specific conversation ID
    sender_id: str
    sender_type: str  # 'user', 'assistant', 'system'
    content: str
    content_type: str  # 'text', 'image', 'voice', etc.
    timestamp: datetime
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Conversation:
    """Unified conversation structure"""
    conversation_id: str
    platform_conversation_id: str
    merchant_id: str
    customer_id: str
    platform: str
    status: str  # 'active', 'closed', 'archived'
    created_at: datetime
    last_updated: datetime
    message_count: int = 0
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class ChatAdapter(Protocol):
    """Protocol for chat adapters"""

    @property
    def platform_name(self) -> str:
        """Platform name (e.g., 'xiaohongshu', 'taobao', 'jd')"""
        ...

    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        Initialize the adapter with platform credentials and settings.

        Args:
            config: Configuration dict containing API keys, webhook URLs, etc.

        Returns:
            True if initialization successful
        """
        ...

    async def send_message(self, conversation_id: str, content: str, **kwargs) -> bool:
        """
        Send a message to a conversation.

        Args:
            conversation_id: Our internal conversation ID
            content: Message content to send
            **kwargs: Additional platform-specific parameters

        Returns:
            True if message sent successfully
        """
        ...

    async def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[ChatMessage]:
        """
        Get conversation history.

        Args:
            conversation_id: Our internal conversation ID
            limit: Maximum number of messages to retrieve

        Returns:
            List of ChatMessage objects
        """
        ...

    async def mark_message_read(self, message_id: str) -> bool:
        """
        Mark a message as read.

        Args:
            message_id: Platform message ID

        Returns:
            True if marked successfully
        """
        ...

    async def get_active_conversations(self, merchant_id: str) -> List[Conversation]:
        """
        Get all active conversations for a merchant.

        Args:
            merchant_id: Merchant identifier

        Returns:
            List of active Conversation objects
        """
        ...

    async def close_conversation(self, conversation_id: str) -> bool:
        """
        Close a conversation.

        Args:
            conversation_id: Our internal conversation ID

        Returns:
            True if closed successfully
        """
        ...

    async def listen_for_messages(self) -> AsyncGenerator[ChatMessage, None]:
        """
        Listen for new incoming messages.
        This is typically implemented as a webhook handler or polling mechanism.

        Yields:
            ChatMessage objects as they arrive
        """
        ...

    async def validate_webhook(self, request_data: Dict[str, Any]) -> bool:
        """
        Validate incoming webhook requests.

        Args:
            request_data: Raw webhook request data

        Returns:
            True if webhook is valid
        """
        ...

    async def get_platform_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get platform user information.

        Args:
            user_id: Platform user ID

        Returns:
            User info dict or None if not found
        """
        ...


class ChatAdapterFactory:
    """Factory for creating chat adapters"""

    _adapters: Dict[str, type] = {}

    @classmethod
    def register(cls, platform: str, adapter_class: type):
        """Register an adapter class for a platform"""
        cls._adapters[platform.lower()] = adapter_class

    @classmethod
    def create(cls, platform: str, config: Dict[str, Any]) -> ChatAdapter:
        """Create an adapter instance for a platform"""
        platform = platform.lower()
        if platform not in cls._adapters:
            raise ValueError(f"No adapter registered for platform: {platform}")

        adapter_class = cls._adapters[platform]
        return adapter_class(config)