# 自研 Local Agent 路线方案

## 1. 当前结论

项目后续主线从“外部 RPA 工具调用后端”调整为：

```text
电商客服页面 / Mock 客服页面
        |
        v
自研 Local Agent
        |
        v
FastAPI 后端 Agent 决策接口
        |
        v
自研 Local Agent 回填、发送、验证、回写结果
```

影刀等外部 RPA 工具保留为可选验证方案，不再作为项目核心执行层。

这样做的原因：

- 毕设系统更完整，消息读取、去重、监听、回填、发送确认都在自己的系统内。
- 当前已完成的 `/api/chat/rpa/message` 可以直接复用为 Local Agent 调用后端的标准接口。
- 后续前端客服工作台可以展示完整闭环，而不是只能展示后端聊天结果。
- Mock 页面可以保证答辩演示稳定，真实平台适配器可以作为扩展示范。

## 2. 角色边界

### FastAPI 后端

负责：

- 接收标准化买家消息。
- 维护会话上下文。
- 调用意图识别、RAG、商家数据、风险策略。
- 返回结构化决策：
  - `recommended_reply`
  - `risk_level`
  - `auto_send_allowed`
  - `auto_send_blockers`
  - `requires_human_review`
  - `handoff_reason`
  - `missing_info`
- 记录 Local Agent 心跳。
- 记录真实发送结果。

### Local Agent

负责：

- 打开或连接客服页面。
- 监听新买家消息。
- 读取商品、订单、买家、页面上下文。
- 生成稳定 `external_conversation_id` 和 `external_message_id`。
- 调用 `/api/chat/rpa/message`。
- 只根据 `decision.auto_send_allowed` 判断是否自动发送。
- 自动回填、点击发送、验证发送结果。
- 调用 `/api/chat/rpa/send-result` 回写成功、失败或转人工结果。
- 定期调用 `/api/local-agent/heartbeat` 上报运行状态。

### Mock 客服页面

负责：

- 提供稳定、可控的电商客服页面测试靶场。
- 用于验证 Local Agent 的完整闭环。
- 不模拟完整电商平台，只模拟必要元素：
  - 会话列表
  - 买家消息区
  - 商品卡片
  - 输入框
  - 发送按钮
  - 转人工标记

## 3. 为什么仍然要做 Mock 页面

Mock 页面不是为了逃避真实平台，而是为了先证明自研 Local Agent 的核心能力：

```text
发现新消息 -> 抽取上下文 -> 调后端 -> 获取决策 -> 回填发送 -> 验证结果 -> 回写后端
```

真实平台适配容易受登录、验证码、iframe、DOM 变化、虚拟滚动、未读标识变化影响。先用 Mock 页面跑通闭环，可以把工程风险拆开：

- MockShopAdapter：验证系统闭环稳定。
- GenericWebChatAdapter / PddWebAdapter：验证真实网页适配可行。

答辩时可以明确说明：

> 系统采用平台适配器模式。MockShopAdapter 用于稳定验证完整链路，真实平台适配器可按同一接口扩展。

## 4. Local Agent 模块设计

建议目录：

```text
app/
  local_agent/
    __init__.py
    runtime.py
    config.py
    adapters/
      base.py
      mock_shop.py
      generic_web_chat.py
      pdd_web.py
    watchers/
      dom_watcher.py
      polling_watcher.py
    extractors/
      message_extractor.py
      context_extractor.py
    executors/
      action_executor.py
      send_verifier.py
    store/
      event_store.py
      deduper.py
      session_queue.py
```

第一版只实现最小可跑闭环：

- `BasePlatformAdapter`
- `MockShopAdapter`
- `EventDeduper`
- `SessionQueue`
- `runtime.py`

后续再补真实平台适配器和更复杂的 watcher。

## 5. 后端新增接口

### 5.1 发送结果回写

```text
POST /api/chat/rpa/send-result
```

用途：

- 记录 Local Agent 是否真的发出消息。
- 记录发送失败原因。
- 给前端工作台展示闭环状态。
- 避免“后端生成了回复，但页面没有成功发送”无法追踪。

请求示例：

```json
{
  "request_id": "7cfa1e3a-bfd8-447b-a673-1d5479b1b917",
  "merchant_id": "default",
  "platform": "pinduoduo",
  "external_conversation_id": "buyer-session-001",
  "external_message_id": "msg-001",
  "send_status": "success",
  "sent_text": "亲，这款目前有现货，可以直接拍。",
  "sent_at": "2026-06-17T10:30:00",
  "agent_id": "local-agent-001",
  "error_code": null,
  "error_message": null
}
```

### 5.2 Local Agent 心跳

```text
POST /api/local-agent/heartbeat
```

用途：

- 判断 Local Agent 是否在线。
- 判断当前监听平台、窗口、店铺是否正常。
- 展示最近读取消息、最近发送消息、异常状态。

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

## 6. 阶段推进

### 阶段 1 收尾：闭环接口补齐

状态：已完成。

目标：

- 新增 `/api/chat/rpa/send-result`
- 新增 `/api/local-agent/heartbeat`
- 文档和执行跟踪同步

验收：

- 能 POST 发送成功结果并查询到记录。
- 能 POST Agent 心跳并查询到最新状态。
- 不影响现有 `/api/chat/rpa/message`。

### 阶段 2：Local Agent 骨架与 Mock 闭环

目标：

- 新建 `app/local_agent`
- 做最小 Mock 客服页面
- Agent 能读取 Mock 页面新消息
- Agent 能调用 `/api/chat/rpa/message`
- `auto_send_allowed=true` 时自动回填发送
- `auto_send_allowed=false` 时标记转人工
- Agent 调用 `/api/chat/rpa/send-result`

验收：

- Mock 页面里输入一条买家消息，Agent 能自动回复。
- 高风险消息不会自动发送。
- 后端能看到发送成功、失败或转人工结果。
- 重复消息不会重复处理。

### 阶段 3：真实平台适配雏形

目标：

- 做 `GenericWebChatAdapter` 或 `PddWebAdapter` 雏形。
- 只验证真实平台页面的关键能力：
  - 读最新买家消息
  - 读商品上下文
  - 回填回复文本
  - 发送前二次确认

验收：

- 至少能在一个真实网页客服环境中完成有限流程验证。
- 真实平台失败时不影响 Mock 演示闭环。

## 7. 当前最优下一步

先做阶段 1 收尾：

1. 新增 `/api/chat/rpa/send-result`。
2. 新增 `/api/local-agent/heartbeat`。
3. 更新接口文档。
4. 更新执行跟踪。

完成后再进入阶段 2：Local Agent 骨架与 Mock 页面闭环。
