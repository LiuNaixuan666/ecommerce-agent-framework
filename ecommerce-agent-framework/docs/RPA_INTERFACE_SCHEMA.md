# RPA 标准接口 Schema

本文档定义本地客服后端给自研 Local Agent / RPA Runtime 调用的稳定接口。当前目标是让执行层只负责三件事：

1. 从平台网页版客服窗口或 Mock 客服页面抓取买家消息和页面上下文。
2. 调用本地后端接口生成客服回复。
3. 只根据 `decision.auto_send_allowed` 决定是否把回复自动发送回平台。

影刀等第三方 RPA 工具可以按同一 schema 调用，但项目主线是自研 Local Agent。

## 1. 接口

`POST /api/chat/rpa/message`

完整本地地址示例：

```text
http://127.0.0.1:8000/api/chat/rpa/message
```

## 2. 请求字段

```json
{
  "merchant_id": "default",
  "platform": "pinduoduo",
  "external_conversation_id": "buyer-session-001",
  "external_message_id": "msg-001",
  "customer_message": "这款有现货吗？",
  "customer_id": "buyer-001",
  "customer_name": "买家昵称",
  "page_context": {
    "platform": "pinduoduo",
    "url": "https://example.com/item/123",
    "title": "儿童科普图书套装",
    "product_name": "儿童科普图书套装",
    "sku": "BOOK-001",
    "price": 59.9,
    "currency": "CNY",
    "stock": 28,
    "stock_status": "in_stock"
  },
  "metadata": {
    "agent_type": "self_built_local_agent",
    "window_title": "拼多多商家后台"
  }
}
```

必填字段：

- `platform`：平台标识，例如 `pinduoduo`、`taobao`、`jd`。
- `external_conversation_id`：平台页面里的买家会话 ID。如果页面拿不到真实 ID，可以用“平台 + 店铺 + 买家昵称/窗口标识”拼出来，但同一个买家会话必须稳定。
- `customer_message`：RPA 抓到的买家最新消息。

建议提供字段：

- `external_message_id`：平台消息 ID 或 RPA 自己生成的消息唯一 ID。提供后，后端可以避免重复处理同一条消息。
- `page_context`：当前商品页或聊天侧边栏里能抓到的商品信息。它会作为结构化证据进入回复生成流程。

## 3. 响应字段

```json
{
  "schema_version": "rpa.message.v1",
  "request_id": "7cfa1e3a-bfd8-447b-a673-1d5479b1b917",
  "merchant_id": "default",
  "platform": "pinduoduo",
  "external_conversation_id": "buyer-session-001",
  "conversation_id": "rpa-...",
  "received_at": "2026-06-12T19:30:00",
  "processed_at": "2026-06-12T19:30:01",
  "message": {
    "external_message_id": "msg-001",
    "customer_message": "这款有现货吗？",
    "duplicate_event": false
  },
  "reply": {
    "recommended_reply": "这款目前有现货，当前库存 28 件。",
    "send_text": "这款目前有现货，当前库存 28 件。"
  },
  "decision": {
    "action": "send",
    "auto_send_allowed": true,
    "risk_level": "low",
    "confidence": 0.72,
    "auto_send_blockers": [],
    "requires_human_review": false,
    "handoff_reason": null,
    "missing_info": []
  },
  "trace": {
    "intent": "PRODUCT_INQUIRY",
    "retrieval_type": "structured",
    "sources": ["structured_data"]
  },
  "rpa_instruction": {
    "should_send": true,
    "should_handoff": false,
    "send_text": "这款目前有现货，当前库存 28 件。",
    "handoff_note": null
  }
}
```

## 4. RPA 执行规则

Local Agent / RPA Runtime 只需要遵守一个核心规则：

```text
如果 decision.auto_send_allowed == true：
    把 rpa_instruction.send_text 填入客服输入框并发送
否则：
    不发送，标记转人工或提醒商家处理
```

不要让执行层自己判断业务风险，也不要让执行层根据关键词二次覆盖后端决策。风险判断统一放在后端 workflow。执行层只做 UI 操作前的二次安全校验，例如当前会话是否匹配、消息是否过期、人工是否已接管、最近是否已发送相同回复。

## 5. 自动发送边界

当前后端只有在以下条件同时满足时才允许自动发送：

- `risk_level == "low"`
- `requires_human_review == false`
- 非澄清回复
- 没有缺失关键信息
- `confidence >= 0.5`
- 有结构化数据或可用知识库证据
- RAG 文档证据与问题足够聚焦

可配置项：

```text
AUTO_SEND_MIN_CONFIDENCE=0.5
AUTO_SEND_ALLOW_MEDIUM_RISK=false
```

默认策略保持保守：中风险不自动发送。如果后续商家明确希望放宽中风险自动发送，可以将 `AUTO_SEND_ALLOW_MEDIUM_RISK` 调整为 `true`，但高风险仍应转人工。

只要出现以下情况之一，就会返回 `auto_send_allowed=false`：

- `risk_medium` 或 `risk_high`
- `human_review_required`
- `clarification_required`
- `missing_info`
- `low_confidence`
- `no_evidence`
- `low_evidence_focus`

## 6. 多平台多会话

后端会用以下三元组映射内部会话：

```text
merchant_id + platform + external_conversation_id
```

因此：

- 不同平台的同名买家不会串上下文。
- 同一平台的不同买家不会串上下文。
- 同一买家的连续消息会复用同一个上下文。

Local Agent 侧必须保证 `external_conversation_id` 对同一个聊天窗口稳定。如果平台拿不到会话 ID，建议先用窗口标题、买家昵称、商品 ID、平台名组合生成一个稳定 ID。

## 7. 重复消息

如果请求里带了 `external_message_id`，后端会记录最近处理过的消息。重复提交同一个 `external_message_id` 时，响应里的：

```json
{
  "message": {
    "duplicate_event": true
  }
}
```

Local Agent 收到 `duplicate_event=true` 时，建议不要重复发送，除非确认平台上一条回复没有发送成功。

## 8. 阶段限制

当前接口只负责“生成决策和回复”，不直接控制平台页面，也不直接调用平台 API。

真正发送动作由 Local Agent 完成。后续发送结果回执接口为：

```text
POST /api/chat/rpa/send-result
```

用于记录平台发送成功、发送失败、窗口失焦、买家会话已关闭等状态。

## 9. 发送结果回写

`POST /api/chat/rpa/send-result`

请求示例：

```json
{
  "request_id": "7cfa1e3a-bfd8-447b-a673-1d5479b1b917",
  "merchant_id": "default",
  "platform": "pinduoduo",
  "external_conversation_id": "buyer-session-001",
  "external_message_id": "msg-001",
  "send_status": "success",
  "sent_text": "这款目前有现货，可以直接拍。",
  "sent_at": "2026-06-17T10:30:00",
  "agent_id": "local-agent-001",
  "error_code": null,
  "error_message": null
}
```

`send_status` 建议枚举：

- `success`
- `failed`
- `handoff`
- `skipped_duplicate`
- `skipped_stale`

查询最近发送结果：

```text
GET /api/chat/rpa/send-results
```

可选查询参数：

- `merchant_id`
- `platform`
- `external_conversation_id`
- `limit`

## 10. Local Agent 心跳

`POST /api/local-agent/heartbeat`

请求示例：

```json
{
  "agent_id": "local-agent-001",
  "merchant_id": "default",
  "platform": "mock_shop",
  "shop_id": "shop_001",
  "status": "running",
  "watched_window_title": "Mock 电商客服工作台",
  "last_message_seen_at": "2026-06-17T10:30:00",
  "last_send_at": "2026-06-17T10:29:50",
  "error_code": null,
  "error_message": null
}
```

`status` 建议枚举：

- `running`
- `paused`
- `stopped`
- `error`

查询 Agent 状态：

```text
GET /api/local-agent/status
GET /api/local-agent/status/{agent_id}
```
