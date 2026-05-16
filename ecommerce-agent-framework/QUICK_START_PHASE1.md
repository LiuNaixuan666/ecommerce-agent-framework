# 🚀 快速入门指南 - Phase 1 功能

> 本指南适用于刚完成第一阶段的系统，展示如何立即使用新的多轮对话和知识管理功能

---

## 📌 目录

1. [快速启动](#快速启动)
2. [多轮对话示例](#多轮对话示例)
3. [文档上传示例](#文档上传示例)
4. [会话管理示例](#会话管理示例)
5. [API 文档](#api-文档)
6. [常见问题](#常见问题)

---

## 快速启动

### Step 1: 启动 API 服务

```bash
cd d:\develop_python\system\ecommerce-agent-framework

# 方式 1：使用 Uvicorn（开发模式）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 方式 2：使用 Python 运行（如果 main.py 有 if __name__ 块）
python app/main.py
```

**输出示例**：
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

### Step 2: 验证服务运行

在浏览器中打开：
- **主页** → http://localhost:8000
- **API 文档** → http://localhost:8000/docs
- **健康检查** → http://localhost:8000/health

---

## 多轮对话示例

### 场景：咨询书籍，然后询问相关问题

#### 请求 1：初始查询（创建新会话）

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "merchant_a",
    "user_query": "《Java编程思想》现在有货吗？"
  }'
```

**响应示例**：
```json
{
  "merchant_id": "merchant_a",
  "user_query": "《Java编程思想》现在有货吗？",
  "response_text": "产品：《Java编程思想》\n价格：89.9 CNY\n库存：45 件 (有货)",
  "intent": "PRODUCT_INQUIRY",
  "confidence": 0.95,
  "sources": ["structured_data"],
  "is_clarification_triggered": false,
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-05-04T10:30:00"
}
```

**记下** `conversation_id` - 这是会话的唯一标识！

#### 请求 2：后续提问（继续同一会话）

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "merchant_a",
    "user_query": "这本书有折扣吗？",
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000"
  }'
```

**响应**：
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "response_text": "根据我们的政策，此商品目前没有折扣，价格为原价 89.9 元。",
  ...
}
```

#### 请求 3：查看完整会话历史

```bash
curl "http://localhost:8000/api/chat/conversations/550e8400-e29b-41d4-a716-446655440000/history"
```

**响应**：
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "merchant_id": "merchant_a",
  "messages": [
    {
      "role": "user",
      "content": "《Java编程思想》现在有货吗？",
      "timestamp": "2024-05-04T10:30:00"
    },
    {
      "role": "assistant",
      "content": "产品：《Java编程思想》...",
      "timestamp": "2024-05-04T10:30:05"
    },
    {
      "role": "user",
      "content": "这本书有折扣吗？",
      "timestamp": "2024-05-04T10:31:00"
    },
    {
      "role": "assistant",
      "content": "根据我们的政策，此商品目前没有折扣...",
      "timestamp": "2024-05-04T10:31:05"
    }
  ],
  "total_count": 4,
  "returned_count": 4
}
```

---

## 文档上传示例

### 场景：上传商家的政策文档

#### Step 1：创建临时文件（用于测试）

```bash
# 创建 policy.txt
echo "我们的退货政策：
- 7天无理由退货
- 保修期：2年
- 运费：满50元包邮" > policy.txt

# 创建 faq.md
echo "# 常见问题

## Q1: 如何联系客服?
A: 联系电话 400-123-4567

## Q2: 支持哪些支付方式?
A: 支持支付宝、微信、银行卡" > faq.md
```

#### Step 2：上传文档

```bash
curl -X POST "http://localhost:8000/api/knowledge/upload?merchant_id=merchant_a" \
  -F "files=@policy.txt" \
  -F "files=@faq.md"
```

**响应**：
```json
{
  "merchant_id": "merchant_a",
  "status": "pending",
  "files_received": 2,
  "upload_id": "abcdef123456",
  "message": "成功接收 2 个文件，已加入摄取队列",
  "timestamp": "2024-05-04T10:35:00"
}
```

**记下** `upload_id` - 用于查询摄取状态！

#### Step 3：查询摄取状态

```bash
# 立即查询（可能还在处理中）
curl "http://localhost:8000/api/knowledge/status/abcdef123456"
```

**响应**：
```json
{
  "merchant_id": "merchant_a",
  "upload_id": "abcdef123456",
  "status": "completed",
  "documents_processed": 2,
  "chunks_created": 15,
  "vector_store_size": 15,
  "progress_percentage": 100,
  "error_message": null,
  "timestamp": "2024-05-04T10:35:30"
}
```

#### Step 4：测试知识检索

```bash
curl -X POST "http://localhost:8000/api/chat/query" \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "merchant_a",
    "user_query": "你们支持哪些支付方式？"
  }'
```

**响应**（从上传的文档中检索）：
```json
{
  "response_text": "根据我们的常见问题，我们支持以下支付方式：\n- 支付宝\n- 微信\n- 银行卡",
  "sources": ["raw_docs"],
  ...
}
```

---

## 会话管理示例

### 获取会话信息

```bash
curl "http://localhost:8000/api/chat/conversations/550e8400-e29b-41d4-a716-446655440000"
```

**响应**：
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "merchant_id": "merchant_a",
  "message_count": 4,
  "created_at": "2024-05-04T10:30:00",
  "last_updated": "2024-05-04T10:31:05",
  "last_intent": "PRODUCT_INQUIRY",
  "status": "active"
}
```

### 列出所有会话

```bash
curl "http://localhost:8000/api/chat/conversations"
```

**响应**：
```json
{
  "total": 2,
  "conversations": [
    {
      "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
      "merchant_id": "merchant_a",
      "message_count": 4,
      "status": "active"
    },
    {
      "conversation_id": "660e8400-e29b-41d4-a716-446655440001",
      "merchant_id": "merchant_a",
      "message_count": 2,
      "status": "active"
    }
  ]
}
```

### 关闭会话

```bash
curl -X POST "http://localhost:8000/api/chat/conversations/550e8400-e29b-41d4-a716-446655440000/close" \
  -H "Content-Type: application/json"
```

**响应**：
```json
{
  "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "closed",
  "message": "会话已关闭"
}
```

---

## API 文档

### 聊天端点

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/chat/query` | POST | 发送查询 | 公开 |
| `/api/chat/conversations` | GET | 列出会话 | 公开 |
| `/api/chat/conversations/{id}` | GET | 获取会话信息 | 公开 |
| `/api/chat/conversations/{id}/history` | GET | 获取会话历史 | 公开 |
| `/api/chat/conversations/{id}/close` | POST | 关闭会话 | 公开 |
| `/api/chat/health` | GET | 健康检查 | 公开 |

### 知识管理端点

| 端点 | 方法 | 功能 | 权限 |
|------|------|------|------|
| `/api/knowledge/upload` | POST | 上传文档 | 公开 |
| `/api/knowledge/status/{upload_id}` | GET | 查询摄取状态 | 公开 |
| `/api/knowledge/ingest` | POST | 手动触发摄取 | 公开 |
| `/api/knowledge/list-uploads` | GET | 列出上传任务 | 公开 |
| `/api/knowledge/health` | GET | 健康检查 | 公开 |

---

## 常见问题

### Q1: conversation_id 保存在哪里？
**A**: 当前存储在内存中（应用内）。建议在前端保存用户端的 conversation_id，以便后续查询。

### Q2: 会话数据会丢失吗？
**A**: 是的，应用重启后内存数据会丢失。生产环境应该迁移到 Redis 或数据库。

### Q3: 支持上传哪些文件格式？
**A**: 目前支持 `.txt`、`.pdf`、`.docx`、`.csv`、`.md`、`.doc`

### Q4: 摄取需要多长时间？
**A**: 取决于文件大小和内容量。通常几秒到几十秒。可通过 `status` 端点实时查询。

### Q5: 可以删除已上传的文档吗？
**A**: 当前版本不支持删除。需要手动删除 `data/merchants/{merchant_id}/raw_docs/` 中的文件。

### Q6: 如何清除会话历史？
**A**: 调用关闭会话端点或删除应用内存（但这会删除所有会话）。

### Q7: 支持并发查询吗？
**A**: 当前支持，但内存存储可能有限制。生产环境建议用数据库。

---

## 🧪 自动化测试脚本

保存为 `test_phase1.sh`：

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"
MERCHANT_ID="merchant_a"

echo "=== Testing Phase 1 Features ==="

# Test 1: Single turn query
echo -e "\n[Test 1] Single turn query..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/chat/query" \
  -H "Content-Type: application/json" \
  -d "{
    \"merchant_id\": \"$MERCHANT_ID\",
    \"user_query\": \"《Java编程思想》有货吗?\"
  }")
CONV_ID=$(echo $RESPONSE | grep -o '"conversation_id":"[^"]*' | cut -d'"' -f4)
echo "Conversation ID: $CONV_ID"

# Test 2: Multi-turn query
echo -e "\n[Test 2] Multi-turn query..."
curl -s -X POST "$BASE_URL/api/chat/query" \
  -H "Content-Type: application/json" \
  -d "{
    \"merchant_id\": \"$MERCHANT_ID\",
    \"user_query\": \"多少钱?\",
    \"conversation_id\": \"$CONV_ID\"
  }" | jq .

# Test 3: Get conversation history
echo -e "\n[Test 3] Get conversation history..."
curl -s "$BASE_URL/api/chat/conversations/$CONV_ID/history" | jq .

# Test 4: Health checks
echo -e "\n[Test 4] Health checks..."
curl -s "$BASE_URL/health" | jq .
curl -s "$BASE_URL/api/chat/health" | jq .
curl -s "$BASE_URL/api/knowledge/health" | jq .

echo -e "\n=== All tests completed ==="
```

运行测试：
```bash
chmod +x test_phase1.sh
./test_phase1.sh
```

---

## 📞 需要帮助？

1. **查看日志**：检查终端输出的日志信息
2. **查看 API 文档**：访问 http://localhost:8000/docs
3. **检查健康状态**：访问 http://localhost:8000/health
4. **查看源代码**：
   - 会话管理：`app/api/routes_chat.py` 第 30-60 行
   - 知识管理：`app/api/routes_knowledge.py` 全文

---

**状态**：✅ Phase 1 功能已就绪
**下一步**：实现前端或扩展功能
