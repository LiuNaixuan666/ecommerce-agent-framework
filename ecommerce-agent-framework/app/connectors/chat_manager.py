# app/connectors/chat_manager.py
"""
Chat Manager for Multi-Platform Conversation Handling

Manages conversations across multiple e-commerce platforms, handles message routing,
and coordinates with the AI engine for responses.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import json

import importlib

from .chat_base import ChatAdapter, ChatMessage, Conversation, ChatAdapterFactory
from ..storage.storage_manager import storage_manager
from ..engine import engine

logger = logging.getLogger(__name__)


class ChatManager:
    """Manages chat conversations across multiple platforms"""

    def __init__(self):
        self.adapters: Dict[str, ChatAdapter] = {}
        self.adapter_modes: Dict[str, str] = {}
        self.active_conversations: Dict[str, Conversation] = {}
        self.message_queue = asyncio.Queue()
        self.processing_tasks: Set[asyncio.Task] = set()
        self.is_running = False

    async def initialize(self, platform_configs: Dict[str, Dict[str, Any]]) -> bool:
        """Initialize chat adapters for configured platforms"""
        try:
            for platform, config in platform_configs.items():
                adapter = None
                adapter_class_path = config.get('adapter_class') or config.get('adapter_class_path')
                listen_mode = config.get('listen_mode', 'polling').lower()
                self.adapter_modes[platform] = listen_mode

                if adapter_class_path:
                    try:
                        module_name, class_name = adapter_class_path.rsplit('.', 1)
                        module = importlib.import_module(module_name)
                        adapter_class = getattr(module, class_name)
                        adapter = adapter_class(config)
                    except Exception as e:
                        logger.warning(f"Failed to import adapter class {adapter_class_path} for platform {platform}: {e}")

                if adapter is None:
                    try:
                        adapter = ChatAdapterFactory.create(platform, config)
                    except Exception as e:
                        logger.warning(f"ChatAdapterFactory could not create adapter for {platform}: {e}")

                if adapter is None:
                    logger.warning(f"No adapter configured for platform {platform}")
                    continue

                success = await adapter.initialize(config)
                if success:
                    self.adapters[platform] = adapter
                    logger.info(f"Initialized adapter for platform: {platform} in mode {listen_mode}")
                else:
                    logger.error(f"Failed to initialize adapter for platform: {platform}")

            return len(self.adapters) > 0

        except Exception as e:
            logger.error(f"Failed to initialize chat manager: {e}")
            return False

    async def start(self):
        """Start the chat manager"""
        if self.is_running:
            return

        self.is_running = True
        logger.info("Starting chat manager...")

        # Start message processing
        processor_task = asyncio.create_task(self._process_message_queue())
        self.processing_tasks.add(processor_task)

        # Start listening on adapters configured for polling
        for platform, adapter in self.adapters.items():
            mode = self.adapter_modes.get(platform, 'polling')
            if mode in ['polling', 'both']:
                listener_task = asyncio.create_task(self._listen_to_adapter(platform, adapter))
                self.processing_tasks.add(listener_task)
                logger.info(f"Started polling listener for {platform}")
            else:
                logger.info(f"Skipping polling listener for {platform} (mode={mode})")

        logger.info(f"Chat manager started with {len(self.adapters)} platforms")

    async def process_webhook_event(self, platform: str, payload: Dict[str, Any]) -> bool:
        """Process an incoming webhook payload for a configured adapter"""
        if platform not in self.adapters:
            logger.error(f"Webhook received for unconfigured platform: {platform}")
            return False

        adapter = self.adapters[platform]

        if hasattr(adapter, 'validate_webhook'):
            try:
                is_valid = await adapter.validate_webhook(payload)
            except Exception as e:
                logger.error(f"Error validating webhook for {platform}: {e}")
                return False
            if not is_valid:
                logger.warning(f"Webhook validation failed for {platform}")
                return False

        if not hasattr(adapter, 'parse_webhook'):
            logger.warning(f"Adapter {platform} does not implement parse_webhook")
            return False

        try:
            message = await adapter.parse_webhook(payload)
            message.metadata['platform'] = platform
            await self.message_queue.put(message)
            logger.info(f"Queued webhook message from {platform}: {message.message_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to parse webhook payload for {platform}: {e}")
            return False

    async def stop(self):
        """Stop the chat manager"""
        if not self.is_running:
            return

        self.is_running = False
        logger.info("Stopping chat manager...")

        # Cancel all processing tasks
        for task in self.processing_tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.processing_tasks, return_exceptions=True)

        # Close adapters
        for adapter in self.adapters.values():
            if hasattr(adapter, 'close'):
                await adapter.close()

        self.processing_tasks.clear()
        logger.info("Chat manager stopped")

    async def send_message(self, platform: str, conversation_id: str, content: str, **kwargs) -> bool:
        """Send a message through a specific platform"""
        if platform not in self.adapters:
            logger.error(f"No adapter for platform: {platform}")
            return False

        adapter = self.adapters[platform]
        return await adapter.send_message(conversation_id, content, **kwargs)

    async def get_conversation_history(self, platform: str, conversation_id: str, limit: int = 50) -> List[ChatMessage]:
        """Get conversation history from a platform"""
        if platform not in self.adapters:
            logger.error(f"No adapter for platform: {platform}")
            return []

        adapter = self.adapters[platform]
        return await adapter.get_conversation_history(conversation_id, limit)

    async def _listen_to_adapter(self, platform: str, adapter: ChatAdapter):
        """Listen for messages from a specific adapter"""
        try:
            if not hasattr(adapter, 'listen_for_messages'):
                logger.warning(f"Adapter {platform} does not support polling listen_for_messages")
                return

            async for message in adapter.listen_for_messages():
                # Add platform info to message
                message.metadata['platform'] = platform

                # Queue message for processing
                await self.message_queue.put(message)
                logger.debug(f"Queued message from {platform}: {message.message_id}")

        except Exception as e:
            logger.error(f"Error listening to {platform}: {e}")
            # Restart listening after delay
            await asyncio.sleep(10)
            if self.is_running:
                asyncio.create_task(self._listen_to_adapter(platform, adapter))

    async def _process_message_queue(self):
        """Process incoming messages from the queue"""
        while self.is_running:
            try:
                # Get message from queue with timeout
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)

                # Process message
                await self._handle_incoming_message(message)

                # Mark task as done
                self.message_queue.task_done()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing message: {e}")

    async def _handle_incoming_message(self, message: ChatMessage):
        """Handle an incoming message"""
        try:
            platform = message.metadata.get('platform', 'unknown')

            # Get or create conversation
            conversation = await self._get_or_create_conversation(message, platform)

            # Store message in our database
            await self._store_message(message, conversation)

            # Check if this is a user message that needs AI response
            if message.sender_type == 'user':
                # Generate AI response
                ai_response = await self._generate_ai_response(message, conversation)

                if ai_response:
                    # Send AI response back through platform
                    success = await self.send_message(
                        platform,
                        message.conversation_id,
                        ai_response
                    )

                    if success:
                        # Store AI response
                        ai_message = ChatMessage(
                            message_id=f"ai_{message.message_id}",
                            conversation_id=message.conversation_id,
                            platform_conversation_id=message.platform_conversation_id,
                            sender_id="ai_assistant",
                            sender_type="assistant",
                            content=ai_response,
                            content_type="text",
                            timestamp=datetime.now(),
                            metadata={"platform": platform, "ai_generated": True}
                        )
                        await self._store_message(ai_message, conversation)

        except Exception as e:
            logger.error(f"Error handling incoming message: {e}")

    async def _get_or_create_conversation(self, message: ChatMessage, platform: str) -> Conversation:
        """Get or create a conversation"""
        conversation_id = message.conversation_id

        # Check if conversation exists in memory
        if conversation_id in self.active_conversations:
            return self.active_conversations[conversation_id]

        # Check database
        stored_conv = storage_manager.get_conversation(conversation_id)
        if stored_conv:
            conversation = Conversation(
                conversation_id=stored_conv['conversation_id'],
                platform_conversation_id=stored_conv.get('platform_conversation_id', ''),
                merchant_id=stored_conv.get('merchant_id', ''),
                customer_id=stored_conv.get('customer_id', ''),
                platform=platform,
                status=stored_conv.get('status', 'active'),
                created_at=datetime.fromisoformat(stored_conv['created_at']),
                last_updated=datetime.fromisoformat(stored_conv['last_updated']),
                message_count=stored_conv.get('message_count', 0),
                metadata=stored_conv.get('metadata', {})
            )
        else:
            # Create new conversation
            conversation = Conversation(
                conversation_id=conversation_id,
                platform_conversation_id=message.platform_conversation_id,
                merchant_id=self._extract_merchant_id(platform),
                customer_id=message.sender_id,
                platform=platform,
                status='active',
                created_at=datetime.now(),
                last_updated=datetime.now(),
                message_count=0
            )

            # Store in database
            conv_data = {
                'conversation_id': conversation.conversation_id,
                'platform_conversation_id': conversation.platform_conversation_id,
                'merchant_id': conversation.merchant_id,
                'customer_id': conversation.customer_id,
                'platform': conversation.platform,
                'status': conversation.status,
                'created_at': conversation.created_at.isoformat(),
                'last_updated': conversation.last_updated.isoformat(),
                'message_count': conversation.message_count,
                'metadata': conversation.metadata
            }
            storage_manager.save_conversation(conversation_id, conv_data)

        # Cache in memory
        self.active_conversations[conversation_id] = conversation
        return conversation

    async def _store_message(self, message: ChatMessage, conversation: Conversation):
        """Store message in database"""
        message_data = {
            'message_id': message.message_id,
            'conversation_id': message.conversation_id,
            'platform_message_id': message.message_id,  # Assuming same for now
            'sender_id': message.sender_id,
            'sender_type': message.sender_type,
            'content': message.content,
            'content_type': message.content_type,
            'timestamp': message.timestamp.isoformat(),
            'metadata': message.metadata
        }

        storage_manager.add_message(message.conversation_id, message_data)

        # Update conversation in session storage and metadata
        conversation.message_count += 1
        conversation.last_updated = datetime.now()

        stored_conv = storage_manager.get_conversation(message.conversation_id) or {}
        stored_conv.update({
            'last_updated': conversation.last_updated.isoformat(),
            'message_count': conversation.message_count
        })
        storage_manager.save_conversation(message.conversation_id, stored_conv)

        conv_data = {
            'last_updated': conversation.last_updated.isoformat(),
            'message_count': conversation.message_count
        }
        storage_manager.update_conversation_metadata(message.conversation_id, conv_data)

    async def _generate_ai_response(self, message: ChatMessage, conversation: Conversation) -> Optional[str]:
        """Generate AI response for user message"""
        try:
            # Get conversation history for context
            history = await self.get_conversation_history(
                conversation.platform,
                conversation.conversation_id,
                limit=10
            )

            # Format history for AI engine
            context_messages = []
            for hist_msg in history[-9:]:  # Last 9 messages + current = 10 total context
                context_messages.append({
                    'role': 'user' if hist_msg.sender_type == 'user' else 'assistant',
                    'content': hist_msg.content
                })

            # Add current message
            context_messages.append({
                'role': 'user',
                'content': message.content
            })

            # Call AI engine
            response = await engine.process_chat_query({
                'merchant_id': conversation.merchant_id,
                'user_query': message.content,
                'conversation_id': conversation.conversation_id,
                'context': context_messages
            })

            return response.get('response_text') if response else None

        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return "抱歉，系统暂时无法处理您的请求，请稍后再试。"

    def _extract_merchant_id(self, platform: str) -> str:
        """Extract merchant ID for platform"""
        # This should be configurable per platform
        # For now, return a default
        return f"{platform}_default_merchant"

    async def get_active_conversations(self, platform: Optional[str] = None) -> List[Conversation]:
        """Get all active conversations, optionally filtered by platform"""
        conversations = []

        if platform and platform in self.adapters:
            adapter = self.adapters[platform]
            conversations = await adapter.get_active_conversations(
                self._extract_merchant_id(platform)
            )
        else:
            # Get from all platforms
            for plat, adapter in self.adapters.items():
                convs = await adapter.get_active_conversations(
                    self._extract_merchant_id(plat)
                )
                conversations.extend(convs)

        return conversations


# Global chat manager instance for application-wide access
chat_manager = ChatManager()