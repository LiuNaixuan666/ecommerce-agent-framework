#!/usr/bin/env python3
"""
小红书平台适配器测试脚本

用于测试小红书API连接和基本功能
"""

import asyncio
import logging
import os
from typing import Dict, Any

from app.connectors.xiaohongshu_adapter import XiaohongshuChatAdapter
from app.config import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_adapter_initialization():
    """测试适配器初始化"""
    logger.info("Testing Xiaohongshu adapter initialization...")

    config = {
        'app_id': settings.xiaohongshu_app_id or 'test_app_id',
        'app_secret': settings.xiaohongshu_app_secret or 'test_app_secret',
        'webhook_token': settings.xiaohongshu_webhook_token or 'test_token',
        'merchant_id': settings.xiaohongshu_merchant_id or 'test_merchant',
        'api_base_url': settings.xiaohongshu_api_base_url
    }

    adapter = XiaohongshuChatAdapter(config)

    try:
        success = await adapter.initialize(config)
        if success:
            logger.info("✅ Adapter initialization successful")
            return adapter
        else:
            logger.error("❌ Adapter initialization failed")
            return None
    except Exception as e:
        logger.error(f"❌ Adapter initialization error: {e}")
        return None


async def test_send_message(adapter: XiaohongshuChatAdapter):
    """测试发送消息"""
    logger.info("Testing message sending...")

    try:
        # 注意：这只是测试代码结构，实际发送需要有效的对话ID
        success = await adapter.send_message(
            conversation_id="test_conversation_123",
            content="这是一条测试消息"
        )
        logger.info(f"Message sending result: {success}")
    except Exception as e:
        logger.error(f"Message sending error: {e}")


async def test_get_conversation_history(adapter: XiaohongshuChatAdapter):
    """测试获取对话历史"""
    logger.info("Testing conversation history retrieval...")

    try:
        # 注意：这只是测试代码结构，实际需要有效的对话ID
        messages = await adapter.get_conversation_history(
            conversation_id="test_conversation_123",
            limit=10
        )
        logger.info(f"Retrieved {len(messages)} messages")
    except Exception as e:
        logger.error(f"Conversation history error: {e}")


async def test_webhook_validation(adapter: XiaohongshuChatAdapter):
    """测试Webhook验证"""
    logger.info("Testing webhook validation...")

    # 模拟webhook数据
    test_data = {
        'timestamp': '1640995200',
        'signature': 'test_signature',
        'data': {'message': 'test'}
    }

    try:
        is_valid = await adapter.validate_webhook(test_data)
        logger.info(f"Webhook validation result: {is_valid}")
    except Exception as e:
        logger.error(f"Webhook validation error: {e}")


async def main():
    """主测试函数"""
    logger.info("Starting Xiaohongshu adapter tests...")

    # 检查配置
    if not any([
        settings.xiaohongshu_app_id,
        settings.xiaohongshu_app_secret,
        settings.xiaohongshu_webhook_token
    ]):
        logger.warning("⚠️  No Xiaohongshu credentials found in config. Using test values.")

    # 测试初始化
    adapter = await test_adapter_initialization()
    if not adapter:
        logger.error("Cannot continue tests without working adapter")
        return

    try:
        # 测试各项功能
        await test_send_message(adapter)
        await test_get_conversation_history(adapter)
        await test_webhook_validation(adapter)

    finally:
        # 清理资源
        if hasattr(adapter, 'close'):
            await adapter.close()
        logger.info("Tests completed")


if __name__ == "__main__":
    # 运行异步测试
    asyncio.run(main())