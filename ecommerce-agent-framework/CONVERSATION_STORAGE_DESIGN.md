# 对话历史存储设计

## 存储策略

### 1. 本地存储 (推荐)
```python
# 会话数据结构
conversation = {
    "conversation_id": "conv_123",
    "platform_conversation_id": "tb_chat_456",  # 平台原始对话ID
    "merchant_id": "merchant_a",
    "platform": "taobao",  # taobao, jd, pdd, etc.
    "customer_id": "customer_789",
    "created_at": "2024-01-01T10:00:00Z",
    "last_updated": "2024-01-01T10:05:00Z",
    "status": "active",  # active, closed, archived
    "message_count": 5,
    "last_intent": "refund_inquiry",
    "metadata": {
        "customer_level": "VIP",
        "total_orders": 15,
        "last_order_date": "2024-01-01"
    }
}

# 消息数据结构
message = {
    "message_id": "msg_123",
    "conversation_id": "conv_123",
    "role": "user",  # user, assistant, system
    "content": "我的订单什么时候发货？",
    "timestamp": "2024-01-01T10:00:00Z",
    "platform_message_id": "tb_msg_456",  # 平台原始消息ID
    "metadata": {
        "intent": "shipping_inquiry",
        "confidence": 0.95,
        "sources": ["shipping_policy.txt"],
        "is_clarification_triggered": false
    }
}
```

### 2. 存储优势
- **上下文保持**: AI能记住用户之前的对话历史
- **意图追踪**: 分析用户对话模式和偏好
- **质量监控**: 记录AI回复质量和用户反馈
- **知识更新**: 从对话中学习新问题模式

### 3. 数据清理策略
- 活跃对话: 实时保留
- 关闭对话: 保留6个月
- 归档对话: 保留1年
- 删除策略: 基于商家设置

## 并发处理设计

### 1. 对话锁机制
```python
# 防止多个AI实例同时回复同一对话
async def acquire_conversation_lock(conversation_id: str) -> bool:
    # Redis分布式锁
    return await redis.set(f"lock:{conversation_id}", "locked", ex=30, nx=True)
```

### 2. 消息队列
- 使用Redis Queue处理并发消息
- 每个平台一个队列
- 自动负载均衡

### 3. 连接池管理
- 限制每个平台的并发连接数
- 实现重试和熔断机制