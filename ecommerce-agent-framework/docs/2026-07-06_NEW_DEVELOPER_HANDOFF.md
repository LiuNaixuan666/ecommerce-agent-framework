# 新开发者交接文档：本地多平台 AI 客服工作台

这份文档是给完全不了解本项目的人看的。目标是让新开发者能快速理解当前架构、已完成内容、如何启动、如何调试，以及下一步应该从哪里写代码。

建议阅读顺序：

1. 本文档：先理解系统整体结构和当前状态。
2. `2026-07-06_CONVERSATION_IMPLEMENTATION_SUMMARY.md`：了解最近一次对话已经改了什么。
3. `2026-07-06_CUSTOMER_SERVICE_HUB_IMPLEMENTATION_PLAN.md`：按后续实施步骤继续开发。

## 1. 项目一句话说明

本项目是一个“无官方平台 API”的本地电商 AI 客服系统。

它不依赖拼多多/闲鱼等平台开放 API，而是让商家在本地 Edge 浏览器中登录平台后台，然后通过 Playwright/RPA 读取页面 DOM、识别买家消息、调用本地 AI 决策、再决定是否回复或转人工。

当前 MVP 优先跑通拼多多：

- 拼多多商品抓取。
- 拼多多客服页监听。
- 本地 AI 推荐回复。
- 转人工规则。
- 多平台客服工作台 UI。
- 历史会话与知识库上传的基础闭环。

## 2. 当前技术栈

后端：

- Python
- FastAPI
- Playwright sync API
- Redis/PostgreSQL 可选，当前也支持内存 fallback
- 本地文件 JSON 存储部分运行时配置
- RAG/向量检索模块已有

前端：

- React
- TypeScript
- Vite
- lucide-react 图标
- 目前大量样式是 inline style

浏览器自动化：

- Edge/Chromium
- Playwright
- 使用本地 profile 保持登录态

## 3. 当前启动方式

项目根目录：

```bash
cd D:\develop_python\system\ecommerce-agent-framework
```

后端当前建议使用 8001：

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

前端：

```bash
cd D:\develop_python\system\ecommerce-agent-framework\frontend
npm run dev
```

访问：

```text
http://127.0.0.1:5173
```

健康检查：

```text
http://127.0.0.1:8001/health
```

注意：

- 当前 `frontend/vite.config.js` 的 `/api` 代理指向 `http://localhost:8001`。
- 之前本机 8000 端口出现过旧进程/僵尸监听，因此临时使用 8001。
- 如果新开发者想恢复 8000，需要同步修改 Vite 代理和启动命令。

## 4. 系统总架构

```text
React 前端
  |
  |-- CustomerServiceHub 客服工作台
  |-- ProductManagement / ProductScrapeWizard 商品管理与抓取
  |-- ChatInterface 知识库聊天与文档上传
  v
FastAPI 后端
  |
  |-- routes_platform_browser.py  控制浏览器页面和后台监听
  |-- routes_chat.py              RPA 消息入口、AI 决策、会话历史
  |-- routes_agent_rules.py       转人工规则配置
  |-- routes_local_agent.py       Local Agent 心跳状态
  |-- routes_platform.py          平台注册和聚合状态
  |-- routes_products.py          商品 CRUD 与商品抓取任务
  |-- routes_knowledge.py         知识库上传与摄取
  v
Local Agent 层
  |
  |-- BrowserSessionManager       打开/复用 Edge 页面，保持登录态
  |-- BrowserPageWatcher          从页面 DOM 读取买家消息
  |-- BrowserPageReplyExecutor    填入/发送/标记转人工
  |-- GenericWebChatAdapter       把 watcher/executor 组合成统一平台适配器
  |-- LocalAgentRuntime           调用后端 AI 决策并执行发送/转人工
  v
Edge/拼多多商家后台页面
```

## 5. 最核心的数据流

### 5.1 用户打开客服工作台

前端入口：

- `frontend/src/App.tsx`
- `frontend/src/components/CustomerServiceHub.tsx`

流程：

1. 用户点击左侧菜单“客服工作台”。
2. React 渲染 `CustomerServiceHub`。
3. 页面轮询这些接口：
   - `GET /api/platform/list`
   - `GET /api/platform-browser/sessions`
   - `GET /api/local-agent/status`
   - `GET /api/platform/{platform}/status`
   - `GET /api/chat/conversations`
   - `GET /api/agent-rules`

### 5.2 打开拼多多客服页

前端点击“打开客服页”：

```text
POST /api/platform-browser/open
```

请求体：

```json
{
  "platform": "pinduoduo",
  "page_type": "chat",
  "headed": true
}
```

后端：

1. `routes_platform_browser.py` 调用 `BrowserSessionManager.open_session()`。
2. 使用平台定义里的 URL 打开拼多多客服页。
3. 使用本地 profile 保持登录态。
4. 返回 session 状态给前端。

### 5.3 启动 AI 监听

前端点击“启动 AI”：

```text
POST /api/platform-browser/start-agent
```

请求体：

```json
{
  "platform": "pinduoduo",
  "page_type": "chat",
  "mode": "dry_run",
  "interval_seconds": 8
}
```

后端：

1. 检查客服页 session 是否存在、是否已登录。
2. 同步保存当前接待模式到 `agent_rule_store`。
3. 启动后台 runner。
4. runner 周期性调用 `_browser_agent_cycle()`。

### 5.4 监听到买家消息后

后台 runner 每轮做：

1. `BrowserPageWatcher.read_events()` 从页面 DOM 识别买家消息。
2. `GenericWebChatAdapter.read_new_messages()` 转成 `PlatformMessage`。
3. `LocalAgentRuntime.process_once()` 调用：

```text
POST /api/chat/rpa/message
```

4. 后端 `routes_chat.py`：
   - 写入本地 conversation；
   - 读取最近历史；
   - 读取转人工规则；
   - 调用 `default_workflow.run()`；
   - 返回推荐回复、风险、是否允许自动发送。

5. `LocalAgentRuntime` 根据后端决策：
   - 如果 `auto_send_allowed=true`，调用 executor 发送；
   - 否则调用 `mark_handoff()` 标记转人工。

6. 结果写回：

```text
POST /api/chat/rpa/send-result
POST /api/local-agent/heartbeat
```

7. 前端轮询状态后展示：
   - 最新买家消息；
   - AI 推荐回复；
   - 风险；
   - blocker；
   - 待人工红点。

## 6. 关键文件解释

### 6.1 前端

#### `frontend/src/App.tsx`

负责根据左侧菜单切换页面。当前“客服工作台”指向：

```tsx
<CustomerServiceHub />
```

#### `frontend/src/components/CustomerServiceHub.tsx`

当前最重要的前端页面。

已有功能：

- 多平台账号列表。
- 登录/监听状态。
- 打开客服页。
- 检测登录。
- 启动/停止 AI。
- 待人工队列 MVP。
- 会话列表和历史消息。
- 右侧 AI 推荐回复。
- 转人工规则读取/保存。
- 优质对话上传知识库。
- 模拟测试 AI 回复。

下一步主要改这里：

- 待人工队列从后端 ticket 接口读取。
- 标记已处理调用后端接口。
- 转回 AI 调用后端接口。
- 敏感词/关键词 UI 可编辑。

#### `frontend/src/components/ProductScrapeWizard.tsx`

拼多多商品抓取向导。

正常流程：

1. 打开平台商品页。
2. 登录。
3. 检测登录。
4. 扫描列表。
5. 勾选商品。
6. 导入。
7. 后端逐个进入详情页补 description。

#### `frontend/src/services/api.ts`

前端 API 类型和请求工具。RPA、知识库上传、模拟聊天等类型在这里。

### 6.2 后端 API 层

#### `app/main.py`

FastAPI 应用入口，注册所有 router。

新增路由时必须在这里 include。

当前重要 router：

```python
app.include_router(chat_router)
app.include_router(knowledge_router)
app.include_router(local_agent_router)
app.include_router(platform_router)
app.include_router(products_router)
app.include_router(agent_rules_router)
app.include_router(platform_browser_router)
```

#### `app/api/routes_platform_browser.py`

控制真实浏览器页面。

重要接口：

- `POST /api/platform-browser/open`
- `POST /api/platform-browser/check-login`
- `POST /api/platform-browser/start-agent`
- `POST /api/platform-browser/stop-agent`
- `GET /api/platform-browser/sessions`

重要逻辑：

- `_run_in_thread()`：把 Playwright sync 调用放到单线程 worker。
- `_browser_agent_cycle()`：后台监听循环每一轮的实际处理逻辑。
- `start_agent()`：启动 AI 监听。
- `stop_agent()`：停止监听。

#### `app/api/routes_chat.py`

聊天与 RPA 决策入口。

重要接口：

- `POST /api/chat/query`：普通聊天/模拟测试。
- `POST /api/chat/rpa/message`：RPA 买家消息入口。
- `POST /api/chat/rpa/send-result`：Local Agent 回写执行结果。
- `GET /api/chat/rpa/send-results`：查看发送结果。
- `GET /api/chat/conversations`
- `GET /api/chat/conversations/{conversation_id}/history`

重点：

- `rpa_message()` 是平台消息进 AI 的核心入口。
- 它会读取 `agent_rule_store.get_rules()`，再把规则传给 `workflow.run()`。

#### `app/api/routes_agent_rules.py`

转人工规则 API。

接口：

- `GET /api/agent-rules?merchant_id=default&platform=pinduoduo`
- `PUT /api/agent-rules`
- `GET /api/agent-rules/list`

#### `app/api/routes_local_agent.py`

保存 Local Agent 心跳状态。

前端通过它知道：

- 哪个平台正在监听；
- 最新买家消息；
- 当前页面 URL；
- AI 推荐回复；
- 风险和 blocker。

#### `app/api/routes_platform.py`

平台注册表和平台聚合状态。

当前平台列表包括：

- 拼多多：active。
- 闲鱼、淘宝/千牛、京东、抖店：coming_soon。

#### `app/api/routes_products.py`

商品管理和商品抓取任务。

关键点：

- 拼多多商品抓取复用平台浏览器页。
- 商品详情抓取也在浏览器 worker 中执行。

### 6.3 Local Agent 层

#### `app/local_agent/runtime.py`

Local Agent 总调度器。

核心方法：

- `process_once(adapter, backend_client)`
- `build_rpa_message_payload()`
- `build_send_result_payload()`
- `decide_execution_text()`

当前行为：

1. 读取 adapter 中的新消息。
2. 调用 `/api/chat/rpa/message`。
3. 根据 `auto_send_allowed` 决定发送或转人工。
4. 调用 `/api/chat/rpa/send-result`。
5. 维护 `_last_decision_snapshot`，保证 AI 推荐回复不被空心跳覆盖。

#### `app/local_agent/browser_session_manager.py`

管理本地浏览器 session。

负责：

- 打开 Edge/Chromium。
- 使用本地 profile。
- 跳转平台页面。
- 检测登录。
- 页面关闭后恢复。
- 复用 chat/products 页面。

#### `app/local_agent/browser/profiles.py`

内置浏览器平台 profile。

当前重要 profile：

- `pinduoduo_web_profile()`
- `browser_mock_profile()`

拼多多 profile 使用 sentinel selector：

```text
__pdd_auto_buyer_messages__
__pdd_auto_reply_input__
__pdd_auto_send_button__
__pdd_auto_sent_messages__
```

这些 selector 不是真实 CSS，而是告诉 watcher/executor 使用拼多多专用 JS 逻辑。

#### `app/local_agent/watchers/browser_page.py`

从浏览器页面读取消息。

对拼多多有专用逻辑：

- `detect_login_status()`
- `_read_pdd_events()`

当前是启发式识别：

- 根据页面文本。
- 根据气泡位置。
- 根据背景色。
- 过滤导航、规则、底部提示、订单区噪声。

后续需要继续增强，减少误判。

#### `app/local_agent/executors/browser_page.py`

负责把 AI 回复填入输入框或发送。

当前模式：

- dry-run：不填入、不发送，只记录。
- auto：允许真实发送。

注意：当前 `assist` 模式在底层仍等同 dry-run。后续要做成“填入输入框但不点击发送”。

#### `app/local_agent/adapters/generic_web_chat.py`

把 watcher、context extractor、executor 组合成统一平台适配器。

LocalAgentRuntime 不直接关心页面 DOM，只关心 adapter 是否实现：

- `read_new_messages()`
- `send_text()`
- `mark_handoff()`
- `health_check()`

### 6.4 AI 决策层

#### `app/agent/workflow.py`

AI 决策核心。

做的事：

1. 意图识别。
2. 商品/订单/政策知识检索。
3. 不确定性判断。
4. 风险判断。
5. 生成回复。
6. 应用转人工规则。
7. 生成 `WorkflowResult`。

重点字段：

```python
auto_send_allowed
auto_send_blockers
requires_human_review
handoff_reason
risk_level
confidence
sources
response_text
```

当前规则已接入：

- mode 不是 auto 时阻止自动发送。
- 高风险阻止自动发送。
- 售后/订单/退款类问题按规则转人工。
- 低置信度按规则转人工。
- 无知识证据按规则转人工。
- 命中敏感词转人工。
- 命中转人工关键词转人工。
- 图片消息转人工。

### 6.5 存储层

#### `app/storage/storage_manager.py`

统一管理会话和知识摄取存储。

当前可能走：

- Redis：会话、消息。
- PostgreSQL：摄取任务、元数据。
- Memory fallback：没连接上时使用内存。

#### `app/storage/rpa_runtime_store.py`

运行时状态存储。

当前是进程内存：

- agent heartbeats。
- send results。

注意：

- 重启后丢失。
- 后续待人工队列不应该继续只放这里，应该做持久化 store。

#### `app/storage/agent_rule_store.py`

规则配置存储。

当前使用：

```text
data/agent_rules.json
```

如果文件不存在，会自动使用默认规则。

注意：

- 这是本地 MVP 实现。
- 后续可以迁移到 Redis/PostgreSQL。

## 7. 当前已完成的功能

### 7.1 商品抓取

已完成：

- 拼多多商品页打开和登录状态复用。
- 商品列表 DOM 解析增强。
- 商品详情页 description 抓取流程。
- 页面关闭后的重新打开能力。

仍需增强：

- 虚拟列表滚动。
- 分页。
- 更多详情字段。
- 抓取失败诊断。
- 多平台商品抓取注册。

### 7.2 客服监听

已完成：

- 拼多多客服页打开。
- 登录检测。
- 后台监听 runner。
- 买家消息识别。
- AI 决策。
- dry-run/handoff/send-result 回写。
- 心跳展示。

仍需增强：

- 当前会话识别。
- 未读会话红点识别。
- 平台历史消息同步。
- assist 模式填入但不发送。
- 真实发送后的确认校验。

### 7.3 客服工作台

已完成：

- `CustomerServiceHub` 聚合页面。
- 平台列表。
- 红点/待人工 MVP。
- AI 推荐回复固定展示。
- 规则读取/保存。
- 历史会话读取。
- 对话上传知识库。
- 模拟测试。

仍需增强：

- 后端持久化待人工队列。
- 标记已处理和转回 AI 的真实接口。
- 关键词/敏感词编辑 UI。
- 桌面通知/提示音。
- 数据统计。

## 8. 当前 API 快速表

### 平台浏览器

```text
GET  /api/platform-browser/sessions
POST /api/platform-browser/open
POST /api/platform-browser/check-login
POST /api/platform-browser/start-agent
POST /api/platform-browser/stop-agent
POST /api/platform-browser/focus
POST /api/platform-browser/refresh
POST /api/platform-browser/close
```

### 平台状态

```text
GET /api/platform/list
GET /api/platform/{platform_code}/status
```

### Local Agent

```text
POST /api/local-agent/heartbeat
GET  /api/local-agent/status
GET  /api/local-agent/status/{agent_id}
```

### 规则配置

```text
GET /api/agent-rules?merchant_id=default&platform=pinduoduo
PUT /api/agent-rules
GET /api/agent-rules/list
```

### 聊天/RPA

```text
POST /api/chat/query
POST /api/chat/rpa/message
POST /api/chat/rpa/send-result
GET  /api/chat/rpa/send-results
GET  /api/chat/conversations
GET  /api/chat/conversations/{conversation_id}
GET  /api/chat/conversations/{conversation_id}/history
POST /api/chat/conversations/{conversation_id}/close
```

### 商品

```text
GET    /api/products
POST   /api/products
POST   /api/products/import-csv
POST   /api/products/scrape/start
GET    /api/products/scrape/status/{task_id}
POST   /api/products/scrape/confirm-import/{task_id}
```

### 知识库

```text
POST /api/knowledge/upload
GET  /api/knowledge/status/{upload_id}
POST /api/knowledge/ingest
GET  /api/knowledge/list-uploads
GET  /api/knowledge/health
```

## 9. 规则配置数据结构

当前规则结构：

```json
{
  "merchant_id": "default",
  "platform": "pinduoduo",
  "mode": "dry_run",
  "auto_send_low_risk": false,
  "confidence_threshold": 0.75,
  "handoff_rules": {
    "keyword": true,
    "image": true,
    "after_sale": true,
    "out_of_knowledge": true,
    "low_confidence": true,
    "timeout": true
  },
  "sensitive_words": ["QQ", "VX", "V信", "微信", "电话", "手机号", "私下", "转账", "支付宝"],
  "handoff_keywords": ["退款", "退货", "投诉", "差评", "人工", "客服主管", "平台介入", "赔偿"],
  "timeout_seconds": 180,
  "fallback_script": "亲，请稍等，这个问题为您转接人工客服确认。"
}
```

规则影响 `WorkflowResult`：

```json
{
  "auto_send_allowed": false,
  "auto_send_blockers": ["risk_medium", "low_confidence"],
  "requires_human_review": true,
  "handoff_reason": "售后、订单或退款类问题按规则转人工; AI 置信度低于规则阈值"
}
```

## 10. 当前容易踩坑的地方

### 10.1 控制台中文乱码

PowerShell 里 `Get-Content` 可能显示中文乱码，但 VS Code 打开文件一般正常。

不要因为 PowerShell 显示乱码就盲目改编码。

### 10.2 后端 8000/8001

本机 8000 曾经被旧进程占用。当前前端代理指向 8001。

如果接口 404，但代码里明明有路由，常见原因是后端旧进程没重启。

验证新路由可以用：

```bash
python -m py_compile app/api/routes_agent_rules.py
```

或用 FastAPI TestClient。

### 10.3 Playwright sync API 不能直接在 async route 里乱用

项目里通过 `_run_in_thread()` 把浏览器操作放到 worker 线程。

新增浏览器相关能力时，要沿用这个模式，不要在 FastAPI async handler 里直接调用 Playwright sync API。

### 10.4 不要破坏浏览器 profile

平台登录态依赖本地 profile。

不要随意删除：

- `data/browser_profiles/`
- `app/local_agent/browser_profiles/`
- 用户 profile 目录相关文件。

### 10.5 RPA 识别拼多多消息是启发式，不是稳定 API

拼多多页面 DOM 会变。当前识别逻辑在：

```text
app/local_agent/watchers/browser_page.py
```

如果误识别，要先加诊断日志和过滤条件，不要直接大改整个 watcher。

### 10.6 当前待人工队列还不是持久化

`CustomerServiceHub` 里现在的待人工主要来自：

- agent heartbeat；
- recent send results；
- 前端本地 dismissed 状态。

刷新后“标记已处理”会丢。

下一步必须做真正的 handoff ticket store。

## 11. 下一步任务：持久化待人工队列

这是新开发者最应该接手的下一步。

### 11.1 目标

把现在前端本地的“待人工处理”变成后端持久化队列。

用户应该能：

1. 看到所有待人工消息。
2. 点“标记处理中”。
3. 点“标记已处理”。
4. 点“转回 AI 接待”。
5. 刷新页面后状态不丢。
6. 左侧平台红点来自后端真实待人工数量。

### 11.2 新增后端文件

建议新增：

```text
app/storage/handoff_store.py
app/api/routes_handoff.py
```

并在 `app/main.py` 注册：

```python
from app.api.routes_handoff import router as handoff_router
app.include_router(handoff_router)
```

### 11.3 Handoff Ticket 模型

建议字段：

```json
{
  "ticket_id": "uuid",
  "merchant_id": "default",
  "platform": "pinduoduo",
  "conversation_id": "local conversation id",
  "external_conversation_id": "platform conversation id",
  "external_message_id": "platform message id",
  "customer_message": "我要退款",
  "recommended_reply": "亲，请稍等，资金问题已为您转接人工客服。",
  "reason": "after_sale_risk",
  "blockers": ["risk_medium", "low_confidence"],
  "risk_level": "medium",
  "confidence": 0.62,
  "status": "pending",
  "assigned_to": null,
  "human_reply": null,
  "created_at": "...",
  "updated_at": "...",
  "resolved_at": null,
  "returned_to_ai_at": null
}
```

状态枚举：

```text
pending
processing
resolved
returned_to_ai
closed
```

### 11.4 Handoff API

建议接口：

```text
GET  /api/handoff/tickets?merchant_id=default&platform=pinduoduo&status=pending
POST /api/handoff/tickets
POST /api/handoff/tickets/{ticket_id}/start
POST /api/handoff/tickets/{ticket_id}/resolve
POST /api/handoff/tickets/{ticket_id}/return-to-ai
POST /api/handoff/tickets/{ticket_id}/close
GET  /api/handoff/summary?merchant_id=default
```

`GET /api/handoff/summary` 返回：

```json
{
  "platforms": {
    "pinduoduo": {
      "pending": 3,
      "processing": 1
    }
  }
}
```

### 11.5 什么时候创建 ticket

在 `app/api/routes_chat.py` 的 `rpa_message()` 中：

1. `workflow_result.auto_send_allowed == false`
2. 或 `workflow_result.requires_human_review == true`
3. 或 `workflow_result.auto_send_blockers` 非空

就创建/更新 ticket。

注意去重：

- 同一个 `merchant_id + platform + external_conversation_id + external_message_id` 不应重复创建多个 ticket。
- 如果没有 `external_message_id`，可用内容 hash。

### 11.6 send-result 也要同步 ticket

在 `rpa_send_result()` 中：

- `send_status == "handoff"`：确保 ticket 存在，状态为 pending。
- `send_status == "success"`：如果同消息有 ticket，可以关闭或标记 resolved。
- `send_status == "failed"`：可创建 ticket，reason 为 send_failed。

### 11.7 前端 CustomerServiceHub 修改点

当前文件：

```text
frontend/src/components/CustomerServiceHub.tsx
```

需要改：

1. 新增 `handoffTickets` state。
2. `loadData()` 里请求：

```text
GET /api/handoff/tickets?merchant_id=default&platform=${selectedPlatform}
GET /api/handoff/summary?merchant_id=default
```

3. 左侧平台红点使用 summary。
4. 待人工队列用 `handoffTickets` 渲染，而不是从 heartbeat/sendResults 临时拼。
5. “标记已处理”调用：

```text
POST /api/handoff/tickets/{ticket_id}/resolve
```

6. “转回 AI 接待”调用：

```text
POST /api/handoff/tickets/{ticket_id}/return-to-ai
```

然后再调用 `/api/platform-browser/start-agent`。

### 11.8 验收标准

完成后必须满足：

1. 触发转人工后，刷新页面仍能看到待人工 ticket。
2. 左侧拼多多图标显示红点。
3. 标记已处理后，ticket 状态变 resolved，红点减少。
4. 转回 AI 后，ticket 状态变 returned_to_ai，AI 监听重新启动。
5. 同一条平台消息不会重复创建 ticket。
6. `npm run build` 通过。
7. Python 编译通过：

```bash
python -m py_compile app/api/routes_handoff.py app/storage/handoff_store.py app/api/routes_chat.py app/main.py
```

## 12. 测试建议

### 12.1 后端接口测试

可以用 FastAPI TestClient，避免本机端口旧进程干扰：

```python
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
res = client.get("/api/agent-rules", params={"merchant_id": "default", "platform": "pinduoduo"})
print(res.status_code, res.json())
```

### 12.2 RPA 决策测试

```python
res = client.post("/api/chat/rpa/message", json={
    "merchant_id": "default",
    "platform": "pinduoduo",
    "external_conversation_id": "test-conv",
    "external_message_id": "test-msg-1",
    "customer_message": "我要退款",
    "page_context": {
        "platform": "pinduoduo",
        "product_name": "测试商品",
        "price": 88,
        "stock": 5
    }
})
print(res.json()["decision"])
```

预期：

- `auto_send_allowed` 为 false。
- blocker 包含 `risk_medium` 或 `handoff_keyword`。

### 12.3 前端测试

```bash
cd frontend
npm run build
```

然后打开：

```text
http://127.0.0.1:5173
```

检查：

1. 客服工作台可打开。
2. 规则 Tab 可读取和保存。
3. 待人工区域渲染正常。

## 13. 编码原则

1. 不要直接依赖平台官方 API。本项目当前路线是本地 RPA。
2. 不要在前端硬编码真实业务状态，状态应从后端接口来。
3. 不要让 AI 在无知识证据、低置信、售后、退款、投诉、敏感词场景自动发送。
4. 不要破坏 dry-run。dry-run 永远不能真实发送。
5. 所有 Playwright 操作必须复用已有浏览器 session 和 worker 线程模式。
6. 所有新增接口都要在 `app/main.py` 注册。
7. 前端新增字段要同步 TypeScript 类型。
8. 修改后至少跑：

```bash
python -m py_compile ...
npm run build
```

## 14. 给新开发者的最短任务说明

如果只给新开发者一个任务，可以这样说：

> 请在当前项目中实现“持久化待人工队列”。先阅读 `docs/2026-07-06_NEW_DEVELOPER_HANDOFF.md` 和 `docs/2026-07-06_CUSTOMER_SERVICE_HUB_IMPLEMENTATION_PLAN.md`。新增 `handoff_store.py` 和 `routes_handoff.py`，让 RPA 决策触发转人工时创建 ticket，前端 `CustomerServiceHub` 从后端 ticket 接口读取待人工队列和平台红点，并支持标记已处理、转回 AI。完成后跑 Python 编译和 `npm run build`。

