# 客服工作台后续详细实施文档

本文档用于指导后续继续实现“本地多平台 AI 客服工作台”。当前已完成前端聚合工作台 MVP 和拼多多 RPA 基础闭环，下一步要把 MVP 做成可持续使用的产品化流程。

如果开发者完全不了解当前项目，请先阅读 `2026-07-06_NEW_DEVELOPER_HANDOFF.md`。该文档包含架构、启动方式、关键文件、数据流、接口和下一步编码任务的详细说明。

## 1. 产品形态

目标参考“蜂答”类聚合工作台，但保持本项目的本地 RPA 技术路线：

1. 左侧显示多平台店铺账号。
2. 有新消息或待人工时，平台/店铺图标右上角出现红点。
3. 中间显示会话列表和聊天历史，不要求用户必须切换到弹出的平台窗口才能看消息。
4. 右侧固定显示 AI 推荐回复、风险等级、置信度和证据来源。
5. AI 不能处理或命中规则时进入“待人工处理”。
6. 人工处理完成后，可以一键转回 AI 接待。
7. 支持捕捉历史对话，编辑成更好的问答，导入知识库。
8. 支持上传优质对话。
9. 支持模拟测试 AI 回复质量。

## 2. 推荐整体架构

```text
Frontend CustomerServiceHub
  |
  |-- platform status / sessions / agent status
  |-- handoff queue
  |-- conversation history
  |-- rule config
  |-- learning draft upload
  |-- simulation
  v
FastAPI backend
  |
  |-- platform browser routes
  |-- local agent heartbeat routes
  |-- chat/rpa routes
  |-- handoff queue routes
  |-- rule config routes
  |-- knowledge upload routes
  v
Local Agent Runtime
  |
  |-- BrowserSessionManager
  |-- BrowserPageWatcher
  |-- BrowserPageExecutor
  |-- GenericWebChatAdapter
  v
Edge/Playwright platform pages
```

## 3. 当前代码入口

### 3.1 前端

1. 客服工作台入口：
   - `frontend/src/App.tsx`
   - `frontend/src/components/CustomerServiceHub.tsx`

2. 商品管理/抓取：
   - `frontend/src/components/ProductManagement.tsx`
   - `frontend/src/components/ProductScrapeWizard.tsx`

3. 知识库聊天和上传：
   - `frontend/src/components/ChatInterface.tsx`
   - `frontend/src/services/api.ts`

4. 旧工作台/可参考代码：
   - `frontend/src/components/PlatformBrowserWorkbench.tsx`
   - `frontend/src/components/MockShopWorkbench.tsx`
   - `frontend/src/components/ReplyStrategy.tsx`

### 3.2 后端

1. 浏览器控制：
   - `app/api/routes_platform_browser.py`
   - `app/local_agent/browser_session_manager.py`

2. 平台注册与状态：
   - `app/api/routes_platform.py`

3. Local Agent 状态：
   - `app/api/routes_local_agent.py`
   - `app/storage/rpa_runtime_store.py`

4. RPA 对话与 AI 决策：
   - `app/api/routes_chat.py`
   - `app/local_agent/runtime.py`
   - `app/agent/workflow.py`

5. 浏览器页面适配：
   - `app/local_agent/browser/profiles.py`
   - `app/local_agent/watchers/browser_page.py`
   - `app/local_agent/executors/browser_page.py`
   - `app/local_agent/adapters/generic_web_chat.py`

6. 商品抓取：
   - `app/api/routes_products.py`
   - `app/local_agent/scrapers/pdd_product_scraper.py`

7. 知识库上传：
   - `app/api/routes_knowledge.py`
   - `app/knowledge/ingestion.py`

## 4. 数据模型设计

### 4.1 会话 Conversation

当前已有 conversation，但后续建议补齐字段：

```json
{
  "conversation_id": "local stable id",
  "merchant_id": "default",
  "platform": "pinduoduo",
  "shop_id": "pdd_shop_001",
  "external_conversation_id": "platform session id",
  "customer_id": "buyer id",
  "customer_name": "buyer display name",
  "status": "active | handoff | closed",
  "processing_status": "ai_running | handoff_required | human_processing | returned_to_ai | closed",
  "last_intent": "refund_request",
  "last_send_status": "success | handoff | failed | skipped_dry_run",
  "message_count": 12,
  "created_at": "...",
  "last_updated": "..."
}
```

### 4.2 Message

```json
{
  "message_id": "local id",
  "conversation_id": "local stable id",
  "role": "user | assistant | assistant_sent | human | system",
  "content": "message text",
  "source": "rpa | local_agent | human | import",
  "platform_message_id": "external message id",
  "created_at": "...",
  "metadata": {
    "risk_level": "low",
    "confidence": 0.91,
    "auto_send_allowed": true,
    "sources": []
  }
}
```

### 4.3 Handoff Ticket

当前还没有正式模型。建议新增：

```json
{
  "ticket_id": "uuid",
  "merchant_id": "default",
  "platform": "pinduoduo",
  "conversation_id": "local stable id",
  "external_conversation_id": "platform session id",
  "customer_message": "我要退款",
  "recommended_reply": "亲，请稍等，资金问题已为您转接人工客服。",
  "reason": "after_sale_risk",
  "status": "pending | processing | resolved | returned_to_ai | closed",
  "assigned_to": null,
  "created_at": "...",
  "updated_at": "...",
  "resolved_text": "人工实际回复",
  "return_to_ai_at": "..."
}
```

### 4.4 Rule Config

建议新增规则配置：

```json
{
  "merchant_id": "default",
  "platform": "pinduoduo",
  "mode": "dry_run | assist | auto",
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
  "sensitive_words": ["QQ", "微信", "电话", "私下", "转账"],
  "handoff_keywords": ["退款", "投诉", "差评", "人工", "客服主管"],
  "timeout_seconds": 180,
  "fallback_script": "亲，请稍等，这个问题为您转接人工客服确认。"
}
```

## 5. 后端接口实施计划

### 5.1 规则配置接口

新增文件建议：

- `app/api/routes_agent_rules.py`
- `app/storage/agent_rule_store.py`

接口：

```text
GET  /api/agent-rules?merchant_id=default&platform=pinduoduo
PUT  /api/agent-rules
```

前端用途：

1. `CustomerServiceHub` 打开时读取规则。
2. 用户切换转人工规则时保存。
3. `workflow.py` 运行时读取规则并参与决策。

### 5.2 待人工队列接口

新增文件建议：

- `app/api/routes_handoff.py`
- `app/storage/handoff_store.py`

接口：

```text
GET  /api/handoff/tickets?merchant_id=default&platform=pinduoduo&status=pending
POST /api/handoff/tickets
POST /api/handoff/tickets/{ticket_id}/resolve
POST /api/handoff/tickets/{ticket_id}/return-to-ai
POST /api/handoff/tickets/{ticket_id}/close
```

触发时机：

1. `/api/chat/rpa/message` 产生 `requires_human_review=true`。
2. `/api/chat/rpa/send-result` 收到 `send_status=handoff`。
3. Local Agent 检测到超时或无法识别页面。

### 5.3 平台历史对话抓取接口

新增接口建议：

```text
POST /api/platform-browser/capture-history
GET  /api/platform-browser/capture-history/{task_id}
```

请求：

```json
{
  "platform": "pinduoduo",
  "page_type": "chat",
  "scope": "current_conversation | visible_conversations | date_range",
  "date_from": "2026-07-01",
  "date_to": "2026-07-06"
}
```

输出：

```json
{
  "task_id": "uuid",
  "status": "completed",
  "conversation_count": 10,
  "message_count": 180,
  "drafts_created": 22
}
```

### 5.4 对话学习接口

短期可继续复用 `/api/knowledge/upload`。

中期建议新增：

```text
POST /api/knowledge/dialogue-drafts
GET  /api/knowledge/dialogue-drafts
PUT  /api/knowledge/dialogue-drafts/{draft_id}
POST /api/knowledge/dialogue-drafts/{draft_id}/approve
POST /api/knowledge/dialogue-drafts/import
```

用途：

1. 抓取历史对话后生成可编辑草稿。
2. 人工修改回答。
3. 只导入确认后的优质问答。
4. 记录知识来源和版本。

## 6. 工作流接入计划

### 6.1 当前 RPA 决策流

```text
BrowserPageWatcher 读取买家消息
  -> LocalAgentRuntime.build_rpa_message_payload
  -> POST /api/chat/rpa/message
  -> default_workflow.run
  -> 返回 recommended_reply / auto_send_allowed / blockers
  -> LocalAgentRuntime 决定 send_text 或 mark_handoff
  -> POST /api/chat/rpa/send-result
  -> heartbeat 更新前端
```

### 6.2 需要加入规则判断

在 `app/agent/workflow.py` 或其上层 RPA route 中加入：

1. 读取当前平台规则。
2. 对买家消息、页面上下文、AI 结果进行规则判断。
3. 规则命中时设置：
   - `auto_send_allowed=false`
   - `requires_human_review=true`
   - `handoff_reason`
   - `auto_send_blockers`

推荐规则顺序：

1. 安全/违规敏感词过滤。
2. 明确售后/退款/投诉。
3. 图片/订单/地址等非文本消息。
4. 知识库无证据。
5. 置信度低。
6. 平台限制或页面异常。

### 6.3 自动发送策略

建议三种模式：

1. `dry_run`
   - 永远不写入平台输入框，不发送。
   - 只记录买家消息、AI 推荐和决策。

2. `assist`
   - 可填入输入框。
   - 不自动点击发送。
   - 人工审核后发送。

3. `auto`
   - 低风险 + 高置信 + 有知识证据时自动发送。
   - 其它全部进入人工。

## 7. 前端实施计划

### 7.1 CustomerServiceHub 第一阶段：已完成

已完成：

1. 多平台账号列表。
2. 红点/待人工提示。
3. 登录/监听状态。
4. 打开客服页。
5. 检测登录。
6. 启动/停止 AI。
7. 待人工队列 MVP。
8. 历史会话查看。
9. AI 推荐回复固定显示。
10. 规则选择 UI。
11. 对话学习上传。
12. 模拟测试。

### 7.2 CustomerServiceHub 第二阶段

需要做：

1. 规则保存到后端。
2. 待人工列表从后端 ticket 接口读取。
3. “标记已处理”调用后端。
4. “转回 AI 接待”调用后端状态流转。
5. AI 推荐回复支持：
   - 复制；
   - 填入平台；
   - 发送；
   - 修改后发送；
   - 修改后学习。

6. 历史会话支持：
   - 搜索；
   - 平台筛选；
   - 时间筛选；
   - 待人工/已回复筛选。

7. UI 状态细化：
   - 未登录；
   - 已登录未监听；
   - 监听中；
   - 页面关闭；
   - selector 异常；
   - 待人工；
   - AI 自动回复成功；
   - 发送失败。

### 7.3 CustomerServiceHub 第三阶段

需要做：

1. 多店铺管理。
2. 多平台同时监听。
3. 声音提醒。
4. 桌面通知。
5. 会话详情中展示商品卡片。
6. 一键打开对应平台会话。
7. 数据统计：
   - 今日接待；
   - 自动回复数；
   - 待人工数；
   - 转人工原因分布；
   - AI 命中率；
   - 知识库命中率。

## 8. 平台 DOM 适配计划

每个平台新增 profile 时，需要填写：

```json
{
  "name": "xianyu_web",
  "platform": "xianyu",
  "start_url": "...",
  "selectors": {
    "buyer_messages": "...",
    "sent_messages": "...",
    "reply_input": "...",
    "send_button": "...",
    "conversation_items": "...",
    "unread_badge": "...",
    "customer_name": "...",
    "product_card": "..."
  },
  "default_conversation_id": "..."
}
```

拼多多目前使用 JS 启发式方案，后续可以沉淀为：

1. 页面诊断脚本。
2. DOM snapshot 保存。
3. selector 自动推荐。
4. 用户手工校准 selector。

## 9. 知识学习实施计划

### 9.1 历史对话转知识

流程：

```text
读取平台历史对话
  -> 清洗系统消息/重复消息/寒暄
  -> 识别商品卡片和上下文
  -> 生成候选 Q/A
  -> 人工编辑确认
  -> 上传知识库
  -> 记录来源 conversation_id/message_id/product_id
```

### 9.2 优质对话上传

支持格式：

1. TXT
2. Markdown
3. CSV
4. Excel

推荐 CSV 字段：

```text
platform,product_id,question,answer,scenario,tags,source,quality_score
```

### 9.3 知识版本

每次导入应记录：

1. 来源。
2. 时间。
3. 操作人。
4. 适用平台。
5. 适用商品。
6. 原始对话。
7. 编辑后的标准回答。

## 10. 模拟测试实施计划

### 10.1 当前已完成

`CustomerServiceHub` 已可输入一个问题，并调用 `/api/chat/query` 查看 AI 回答。

### 10.2 后续增强

新增测试集：

```json
{
  "case_id": "uuid",
  "merchant_id": "default",
  "platform": "pinduoduo",
  "product_id": "pdd_123",
  "question": "这款可以退吗？",
  "expected_keywords": ["七天无理由", "不影响二次销售"],
  "should_handoff": false,
  "risk_level": "low"
}
```

新增评估输出：

```json
{
  "case_id": "uuid",
  "answer": "...",
  "passed": true,
  "score": 0.86,
  "issues": [],
  "sources": []
}
```

## 11. 验收标准

### 11.1 商品抓取

1. 登录后不重复要求登录。
2. 页面关闭后能重新打开。
3. 能抓到当前商品列表。
4. 能进入详情页补 description。
5. 抓取失败能显示明确原因。
6. 抓取结果能导入商品库。

### 11.2 客服工作台

1. 打开客服页并登录后，前端状态显示已登录。
2. 启动 AI 后状态显示监听中。
3. 买家发消息后，工作台能显示最新买家消息。
4. AI 推荐回复固定显示，不因刷新消失。
5. 命中规则时进入待人工。
6. 左侧平台出现红点。
7. 人工处理后可以转回 AI。
8. 历史会话能查看。
9. 优质对话能上传知识库。
10. 模拟测试能返回 AI 回答。

### 11.3 决策安全

1. 知识库无依据时不自动回复。
2. 售后、退款、投诉默认转人工。
3. 低置信度默认转人工。
4. 敏感词默认拦截或转人工。
5. dry-run 模式永远不发送。

## 12. 推荐下一步开发顺序

### Step 1：持久化规则配置（已完成基础版）

1. 新增规则 store。
2. 新增规则 API。
3. 前端规则 Tab 读取/保存规则。
4. `workflow.py` 接入规则。

本步已完成基础版：

- 新增 `app/storage/agent_rule_store.py`，使用 `data/agent_rules.json` 做本地 JSON 持久化。
- 新增 `app/api/routes_agent_rules.py`。
- `app/main.py` 已注册规则路由。
- `CustomerServiceHub` 已接入规则读取和保存。
- `workflow.py` 已按规则影响 `auto_send_allowed`、`auto_send_blockers` 和 `handoff_reason`。
- `start-agent` 会同步当前接待模式到规则配置。

后续增强：

- 规则配置迁移到 Redis/PostgreSQL。
- 增加关键词/敏感词可编辑 UI。
- 增加规则变更审计。
- 区分平台级规则、店铺级规则、商品级规则。

### Step 2：持久化待人工队列

1. 新增 handoff ticket store。
2. RPA handoff 时创建 ticket。
3. 前端从 ticket API 读取待人工。
4. 支持 resolve/return-to-ai。

### Step 3：完善平台聊天历史读取

1. 当前会话历史读取。
2. 可见会话列表读取。
3. 对话去重。
4. 写入本地 conversation。

### Step 4：对话学习草稿

1. 从历史对话生成问答草稿。
2. 前端编辑确认。
3. 导入知识库。

### Step 5：商品抓取继续增强

1. 商品列表滚动和分页。
2. 详情页字段稳定化。
3. 失败诊断。

### Step 6：接入第二个平台

建议优先闲鱼，因为用户目标里明确提到闲鱼。

需要先做：

1. 闲鱼登录页/客服页 URL。
2. DOM 诊断。
3. selector profile。
4. 消息读取。
5. 输入框/发送按钮执行。
6. 工作台平台状态接入。

## 13. 当前开发命令

前端：

```bash
cd D:\develop_python\system\ecommerce-agent-framework\frontend
npm run dev
```

后端当前开发端口：

```bash
cd D:\develop_python\system\ecommerce-agent-framework
python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

验证：

```bash
python -m py_compile app/local_agent/runtime.py app/api/routes_chat.py
cd frontend
npm run build
```

健康检查：

```text
http://127.0.0.1:8001/health
http://127.0.0.1:5173
```

## 14. 2026-07-08 智能客服推荐与作用域补充

本轮目标：把“拼多多客服、Mock 工作台、知识库聊天共用同一个客服大脑，但数据需要按商家/平台/店铺隔离”落到代码里。

### 14.1 已完成

1. `app/agent/product_recommender.py`
   - 修复推荐关键词和预算解析。
   - 支持“推荐、预算、适合、还有、别的、其他、换一个”等买家表达。
   - 从本地商品库按 `merchant_id + platform + shop_id` 过滤商品。
   - 输出结构化推荐证据：商品标题、价格、库存、类目、推荐原因。

2. `app/agent/workflow.py`
   - `CustomerServiceWorkflow` 接入 `ProductRecommender`。
   - 推荐证据进入 `RetrievalBundle.structured_data`。
   - 对推荐类问题优先生成结构化推荐回复。
   - 页面商品上下文匹配不再硬编码 `merchant_id="default"`，改为使用当前请求的 `merchant_id`。
   - 页面上下文保留 `platform`、`shop_id`、`platform_product_id`，为后续多平台隔离做基础。

3. `app/storage/product_store.py`
   - 商品列表支持 `shop_id` 过滤。
   - `find_by_context()` 支持 `shop_id`，避免不同店铺同平台商品互相误匹配。

4. `app/api/routes_products.py`
   - 商品列表接口支持 `shop_id` 查询参数。

5. `frontend/src/services/api.ts`
   - `fetchChatResponse()` 支持传 `page_context`。

6. `frontend/src/components/CustomerServiceHub.tsx`
   - “模拟测试”调用 `/api/chat/query` 时会带上当前 `platform`、`shop_id`、当前会话标识。
   - 后续测试拼多多客服回答时，不再只是裸测 default 知识库。

### 14.2 当前结论

当前智能客服核心仍然是同一个 `CustomerServiceWorkflow`：

- 知识库聊天：直接调用 `/api/chat/query`。
- Mock 工作台：模拟平台消息，调用 `/api/chat/rpa/message`。
- 拼多多客服：浏览器监听真实页面消息，再调用 `/api/chat/rpa/message`。

区别在于入口和上下文不同，不是三套独立 AI。

### 14.3 仍需继续做

1. 把知识库上传也改成支持 `platform`、`shop_id` 元数据。
2. RAG 检索时支持按 `platform/shop_id` 过滤，而不只是按 `merchant_id` collection 隔离。
3. 商品导入、商品抓取、优质对话学习都统一写入同一个作用域模型：
   - `merchant_id`
   - `platform`
   - `shop_id`
   - `product_id`
4. 客服页模拟测试需要支持选择“当前商品”或“某个商品”后再提问。
5. 推荐系统需要进一步增强：
   - 预算过滤
   - 类目过滤
   - 库存过滤
   - 多商品对比
   - 推荐理由可解释
   - 不足信息时追问

### 14.4 验证记录

已通过：

```bash
python -m py_compile app\agent\product_recommender.py app\agent\workflow.py app\storage\product_store.py app\api\routes_products.py
cd frontend
npm run build
```

手动 workflow 验证：

- 输入：预算 50 以内，有没有适合一年级的图书推荐？
- 结果：`intent=PRODUCT_INQUIRY`
- 结果：`retrieval_type=structured`
- 结果：返回本地商品库中符合预算和库存条件的商品推荐。
## 15. 2026-07-09 知识库按平台/店铺隔离补充

本轮目标：把“优质对话/知识文档上传后只服务当前平台或店铺”的能力落到 RAG 链路里，避免拼多多客服误用图书知识库、Mock 知识库或其他平台资料。

### 15.1 已完成

1. `app/api/routes_knowledge.py`
   - `/api/knowledge/upload` 新增可选表单字段：`platform`、`shop_id`。
   - 上传任务 `task_data` 保存 `product_id/platform/shop_id`。
   - 后台摄取 `_background_ingest_task()` 会把 `product_id/platform/shop_id` 传给 ingestion。
   - 手动摄取 `/api/knowledge/ingest` 会从历史任务里继续读取这些 scope 字段。
   - `/api/knowledge/list-uploads` 返回任务的 `product_id/platform/shop_id`，便于前端后续展示来源。

2. `app/knowledge/ingestion.py`
   - `ingest_merchant_documents()` 新增 `platform`、`shop_id` 参数。
   - 切块时把这些参数继续传给 `split_documents()`。

3. `app/knowledge/chunking.py`
   - 每个 chunk 的 metadata 现在可包含 `product_id`、`platform`、`shop_id`。
   - Chroma 向量库可以据此按商品、平台、店铺过滤。

4. `app/rag/retriever.py`
   - `Retriever.retrieve()` 新增 `platform`、`shop_id` 参数。
   - 检索过滤策略：
     - 有 `product_id + platform + shop_id` 时，优先查精确商品/平台/店铺资料。
     - 商品级资料不足时，只退回同平台/同店铺资料。
     - 只有平台或店铺 scope 时，不再退回全局资料，避免跨平台串知识。
     - 不传平台/店铺时，保持原来的商家级全局检索行为。

5. `app/agent/workflow.py`
   - RAG 检索时从 `page_context` 读取 `platform/shop_id` 并传给 `Retriever`。
   - 拼多多客服、模拟测试等传入平台上下文后，会优先使用对应平台/店铺的知识。

6. `frontend/src/components/CustomerServiceHub.tsx`
   - “对话学习/上传到知识库”现在会随表单一起提交 `merchant_id/platform/shop_id`。
   - 后续从拼多多客服页整理的优质对话，不会默认混进无平台 scope 的通用知识库。

### 15.2 当前数据隔离结论

当前系统隔离层级如下：

1. `merchant_id`：最外层隔离，决定 Chroma collection 和本地数据目录。
2. `platform`：平台隔离，例如 `pinduoduo`、`xianyu`、`mock`。
3. `shop_id`：同一商家在同一平台下的店铺隔离，目前依赖浏览器会话或后续平台适配器提供。
4. `product_id`：商品级隔离，适合商品详情、商品专属问答、售后规则。

长期数据模型应统一成：

```text
merchant_id
  └── platform
        └── shop_id
              └── product_id / conversation_id / knowledge chunks
```

### 15.3 待继续

1. 平台浏览器会话需要稳定产出 `shop_id`，否则只能做到平台级隔离。
2. 商品导入和平台抓取时也应写入 `platform/shop_id`，保证商品推荐和商品问答同一个 scope。
3. 知识库聊天页面可以增加 scope 选择器：通用知识库、拼多多知识库、某个店铺知识库、某个商品知识库。
4. Mock 工作台也应明确传 `platform=mock` 或具体测试平台，避免和真实平台混用。
5. 增加一个可视化“知识来源”面板，显示本次回答用了哪些 chunk、它们来自哪个平台/店铺/商品。

### 15.4 验证记录

已通过：

```bash
python -m py_compile app\api\routes_knowledge.py app\knowledge\ingestion.py app\knowledge\chunking.py app\rag\retriever.py app\agent\workflow.py
cd frontend
npm run build
```

轻量验证：

```text
_metadata_filter(product_id='p1', platform='pinduoduo', shop_id='s1')
=> {'$and': [{'product_id': 'p1'}, {'platform': 'pinduoduo'}, {'shop_id': 's1'}]}

_fallback_filter(product_id='p1', platform='pinduoduo', shop_id='s1')
=> {'$and': [{'platform': 'pinduoduo'}, {'shop_id': 's1'}]}
```

## 16. 2026-07-09 知识来源 / 证据面板

本轮目标：让智能客服回答不再只是给出“推荐回复”，而是能显示本次回答参考了哪些知识来源，便于判断 AI 是依据商品库、结构化商品信息，还是 RAG 知识库片段作答。

### 16.1 已完成

1. `app/agent/workflow.py`
   - `RetrievalBundle` 新增 `evidence_sources`。
   - 支持三类来源：
     - `product_recommendation`：商品推荐结果，来自本地商品库。
     - `structured_data`：页面上下文、商品详情、政策等结构化资料。
     - `rag_chunk`：向量知识库检索到的文档片段。
   - `WorkflowResult` 新增 `evidence_sources` 字段。
   - `/api/chat/query` 返回体会携带 `evidence_sources`。

2. `app/api/routes_chat.py`
   - `ChatResponse` 新增 `evidence_sources`。
   - RPA 消息处理 trace 中新增 `evidence_sources`。
   - 拼多多客服监听拿到买家消息后，AI 决策结果会把知识来源一起回传。

3. `app/local_agent/runtime.py`
   - Local Agent 心跳 metadata 新增：
     - `intent`
     - `retrieval_type`
     - `sources`
     - `evidence_sources`
   - 客服工作台右侧面板可以读取最近一次 AI 决策的证据来源。

4. `frontend/src/services/api.ts`
   - 新增 `EvidenceSource` 类型。
   - `ChatResponseData`、`RpaMessageResponse.trace`、`AgentMetadata` 均支持 `evidence_sources`。

5. `frontend/src/components/CustomerServiceHub.tsx`
   - 右侧“AI 推荐回复”固定展示“知识来源”面板。
   - 模拟测试结果下方也展示“知识来源”面板。
   - 每条来源显示：
     - 来源类型：推荐 / 结构化 / RAG
     - 相似度或分数
     - 平台、店铺、商品 ID、SKU
     - 内容预览片段

### 16.2 当前效果

客服页现在能回答两个关键问题：

1. AI 推荐回复是什么。
2. 这个回复主要参考了哪些资料。

这对后续排查“为什么 AI 没答对”“是不是串用了别的平台知识库”“是否用了错误商品信息”很重要。

### 16.3 仍需继续

1. 在知识来源面板里增加“点击查看完整片段”。
2. 在 RAG chunk 来源中补充更友好的文档标题，而不是只显示 `source`。
3. 对“商品推荐”来源展示商品价格、库存、推荐理由。
4. 给“没有知识来源但 AI 仍回答”的情况增加风险提示。
5. 把知识来源记录持久化到会话历史，避免刷新后只看到最后一次心跳里的来源。

### 16.4 验证记录

已通过：

```bash
python -m py_compile app\agent\workflow.py app\api\routes_chat.py app\local_agent\runtime.py
cd frontend
npm run build
```

## 17. 2026-07-09 会话历史保存知识来源

本轮目标：实时推荐区中的知识来源不能只存在于 Local Agent 心跳中。AI 回答写入会话历史时，也必须保存当次检索证据，保证刷新页面、切换会话后仍可追溯。

### 17.1 已完成

1. `app/api/routes_chat.py`
   - 新增统一的 `_workflow_message_metadata()`。
   - 普通 `/api/chat/query` 与 RPA `/api/chat/rpa/message` 写入 AI 消息时统一保存：
     - `intent`
     - `confidence`
     - `retrieval_type`
     - `sources`
     - `evidence_sources`
     - `risk_level`
     - `auto_send_allowed`
     - `auto_send_blockers`
     - `requires_human_review`
   - RPA 消息额外保留 `request_id`，便于与发送结果关联。
2. `app/models/schemas.py`
   - `ConversationMessage` 新增 `metadata` 字段。
   - 修复历史接口经过 Pydantic 响应模型后丢弃证据元数据的问题。
3. `frontend/src/components/CustomerServiceHub.tsx`
   - 历史会话中的每条 AI 回答会读取 `metadata.evidence_sources`。
   - 有证据时在回答下方显示紧凑版“知识来源”；买家消息和没有来源的旧消息不额外占用空间。
4. `tests/test_chat_evidence_history.py`
   - 验证 workflow 证据可写入消息元数据。
   - 验证历史响应消息模型不会过滤 `metadata`。

### 17.2 数据结构

```json
{
  "role": "assistant",
  "content": "AI 推荐回复",
  "timestamp": "2026-07-09T12:00:00",
  "metadata": {
    "intent": "product_info",
    "retrieval_type": "hybrid",
    "sources": ["catalog"],
    "evidence_sources": [
      {
        "type": "rag_chunk",
        "source": "catalog",
        "platform": "pinduoduo",
        "shop_id": "shop-1",
        "product_id": "product-1",
        "score": 0.91,
        "preview": "命中的知识片段"
      }
    ]
  }
}
```

### 17.3 存储边界

证据现在会跟随会话消息进入 `storage_manager`。页面刷新和会话切换不会丢失；后端进程重启后是否保留，取决于会话存储配置：

- `SESSION_STORAGE=redis`：由 Redis 持久化策略决定。
- 默认内存存储：后端进程重启后会话与证据都会清空。

生产环境需要启用 Redis 或增加数据库会话存储，不能把默认内存后端当成永久历史库。

### 17.4 验证记录

```bash
python -m pytest tests/test_chat_evidence_history.py -q
python -m py_compile app/models/schemas.py app/api/routes_chat.py
cd frontend
npm run build
```

## 18. 2026-07-09 会话永久存储与 Redis 缓存

### 18.1 目标架构

```text
业务接口 / CustomerServiceWorkflow
              |
              v
      LayeredSessionStorage
        |               |
        v               v
 PostgreSQL 主存储    Redis 实时缓存
 永久会话与消息       活跃会话、短期消息副本
```

原则：

1. PostgreSQL 是会话和消息的事实来源，保存完整 AI 证据元数据。
2. Redis 只承担实时缓存，TTL 或缓存淘汰不能导致永久历史丢失。
3. PostgreSQL 不可用时可降级到 Redis；两者都不可用时降级到内存，保证本地开发仍可启动。
4. 不把 Chroma 向量知识库混入会话数据库；Chroma 继续负责语义检索。

### 18.2 实施任务与进度

| 任务 | 状态 | 完成记录 |
|---|---|---|
| 审查现有 Redis/PostgreSQL/内存存储 | 已完成 | PostgreSQL 仅有会话摘要，Redis 有 TTL 和 100 条上限 |
| 新增 `conversation_messages` 永久消息表 | 已完成 | 消息正文、角色、时间和 JSON 证据元数据 |
| PostgreSQL 实现完整 SessionStorage 接口 | 已完成 | 会话、消息、分页、删除、列表、统计 |
| 新增 Redis + PostgreSQL 双层存储 | 已完成 | PostgreSQL 为主，Redis 缓存；历史读取以数据库为准 |
| 增加 `SESSION_STORAGE=postgres/hybrid` | 已完成 | 保持 memory/redis 兼容并支持服务不可用降级 |
| 增加自动化测试 | 已完成 | SQLite 文件重连测试永久层，内存 backend 测试双层逻辑 |
| 配置说明与验收 | 已完成 | 本机 PostgreSQL 18 与 Redis 真实双层读写通过 |

### 18.3 计划数据表

`conversations`

- 会话主键、商家、状态、意图、消息数和更新时间。
- 增加 JSON 扩展数据，保存平台、店铺、外部会话 ID、客户信息和 RPA 状态。

`conversation_messages`

- 自增消息 ID。
- `conversation_id` 外键。
- `role`、`content`、`created_at`。
- `metadata JSON`，保存 intent、risk、retrieval_type、evidence_sources、发送结果等。

### 18.4 推荐配置

```env
SESSION_STORAGE=hybrid
INGESTION_STORAGE=postgres

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=ecommerce_agent
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_SESSION_TTL=86400
```

### 18.5 完成记录

代码：

1. `app/models/database.py`
   - `conversations` 增加 `metadata` JSON 扩展字段。
   - 新增 `conversation_messages`，永久保存消息及 AI 证据。
2. `app/storage/postgres_storage.py`
   - 实现完整会话存储接口。
   - 支持旧 `conversations` 表自动补充 `metadata` 字段。
   - 历史消息按最新消息分页查询，返回时恢复为正序。
3. `app/storage/storage_manager.py`
   - 新增 `LayeredSessionStorage`。
   - 支持 `memory`、`redis`、`postgres`、`hybrid` 四种会话模式。
   - hybrid 写入 PostgreSQL 和 Redis，历史查询以 PostgreSQL 为准。
   - hybrid 首次启动会迁移 Redis 中仍存活的会话；仅当 PostgreSQL 对应会话尚无消息时复制缓存消息，避免覆盖永久历史。
4. `app/storage/redis_storage.py`
   - 删除会话时同步删除消息缓存。
   - 会话列表和统计不再把消息 key 误算为会话。
5. `.env`
   - 当前本机已切换为 `SESSION_STORAGE=hybrid`。
6. `tests/test_session_persistence.py`
   - 覆盖数据库重连后消息和证据仍存在。
   - 覆盖消息替换、分页、删除、双写、数据库优先和缓存回填。
   - 覆盖 Redis 旧会话迁移且不覆盖 PostgreSQL 已有消息。
7. `app/rag/vector_store.py`
   - 对不符合 Chroma 规则的商家 ID 生成稳定且合法的 collection name。
   - 修复单个测试商家目录导致整个 engine 启动初始化失败的问题。

真实环境验证：

```text
session_mode=hybrid
session_backend=LayeredSessionStorage
postgres_connected=True
redis_connected=True
hybrid_smoke_test=passed
cleanup=passed
```

表结构：

```text
conversations:
id, merchant_id, created_at, last_updated, last_intent,
status, message_count, metadata

conversation_messages:
id, conversation_id, role, content, created_at, metadata
```

### 18.6 验证结果

通过：

```text
Python 编译检查：通过
本轮存储与主流程回归：26 passed
前端 npm run build：通过
真实 PostgreSQL + Redis 双层烟雾测试：通过
后端与前端代理健康检查：healthy
```

旧 Redis 活跃会话迁移结果：

```text
迁移前 PostgreSQL conversation_messages=0
迁移后 PostgreSQL conversation_messages=2
SESSION_STORAGE=hybrid
后端地址=http://127.0.0.1:8003
前端地址=http://127.0.0.1:5173
```

旧测试基线升级前现状：

```text
108 passed, 24 failed
```

24 个失败主要来自旧测试仍在 mock 已移除的 `app.agent.intent_parser.OpenAI`、
旧 Local Agent 心跳次数断言和旧不确定性提示文案，不是本轮存储实现造成。
升级前，根目录直接执行 `pytest` 会误收集 UTF-16 的 `tests_run_output.txt`。该问题已在第 19 节通过 `pytest.ini` 修复。

```bash
python -m pytest -q
```

后续应单独安排“旧测试基线升级”，不能把这些失败误认为 PostgreSQL/Redis 持久化失败。

## 19. 2026-07-09 旧测试基线升级

### 19.1 目标

建立与当前架构一致的全量测试基线。处理失败时遵循以下原则：

1. 当前产品行为正确、测试依赖旧接口：更新测试。
2. 测试暴露真实功能回归：修复业务代码。
3. 不通过放宽断言、删除覆盖范围或隐藏失败来制造“全绿”。
4. 测试不得依赖真实 OpenAI、Gemini、PostgreSQL 或 Redis 才能运行。

### 19.2 初始失败分类

基线：

```text
python -m pytest tests -q
108 passed, 24 failed
```

| 分类 | 数量 | 初步原因 | 状态 |
|---|---:|---|---|
| `test_intent_parser.py` | 10 | mock 已移除的 `app.agent.intent_parser.OpenAI`，仍使用旧 `api_key` 构造参数 | 已完成 |
| `test_e2e_workflow.py` | 10 | 同上，并假设所有意图识别都调用 OpenAI | 已完成 |
| `test_ingestion.py` | 1 | patch 旧 embedding 实现路径 | 已完成 |
| `test_local_agent_mock.py` | 2 | 当前每次决策后会增加一次状态心跳 | 已完成 |
| `test_uncertainty_detector.py` | 1 | 断言旧 clarification 文案，当前策略为谨慎回答/转人工 | 已完成 |
| pytest 收集配置 | - | 根目录 UTF-16 `tests_run_output.txt` 被误当 doctest | 已完成 |

### 19.3 当前正确契约

`IntentParser`：

- 构造参数为 `IntentParser(llm=None)`。
- 高置信度规则命中时不调用 LLM。
- 规则置信度不足时调用注入对象的 `chat(messages, **kwargs)`。
- LLM 失败、JSON 非法或字段缺失时退回规则结果。
- 测试通过 Fake LLM 注入，不 patch OpenAI SDK。

`LocalAgentRuntime`：

- 每轮轮询有基础心跳。
- 处理消息后还有决策状态心跳，用于将推荐回复、风险和证据固定展示在工作台。

`UncertaintyDetector`：

- 低置信度统一标记 `is_uncertain=True`。
- 推荐文本允许采用澄清、谨慎回答或转人工策略；测试应验证决策语义，不绑定过时的唯一文案。

### 19.4 实时进度

| 步骤 | 状态 | 结果 |
|---|---|---|
| 失败分类与当前契约确认 | 已完成 | 24 个失败分为 5 组 |
| IntentParser 测试升级 | 已完成 | Fake LLM 注入；15 passed |
| E2E workflow 测试升级 | 已完成 | 当前规则、降级、决策与多轮契约；11 passed |
| 摄取测试升级 | 已完成 | 依赖注入 MockEmbeddings，并 patch 当前 vector store 工厂；1 passed |
| Local Agent 心跳测试升级 | 已完成 | 验证基础心跳、决策心跳及持久展示元数据；相关组合 40 passed |
| Uncertainty 测试升级 | 已完成 | 明确阈值相等时采用谨慎回答，低于阈值才触发 LOW_RETRIEVAL |
| pytest 收集配置 | 已完成 | 新增 `pytest.ini`，根目录只收集 `tests/test_*.py` |
| 测试环境隔离 | 已完成 | `tests/conftest.py` 强制内存存储和本地模型，不写真实 PostgreSQL/Redis |
| 全量回归 | 已完成 | `137 passed, 0 failed` |

### 19.5 真实代码修复

本轮并非只有测试更新。测试审查发现 Local Agent 对旧响应格式的兼容缺口：

- 自动发送逻辑能够使用响应顶层的 `recommended_reply`。
- 决策心跳原先只读取 `reply.recommended_reply` 或 `decision.recommended_reply`。
- 当后端返回旧格式顶层字段时，消息会正常发送，但工作台心跳缺少推荐回复。
- `app/local_agent/runtime.py` 已增加顶层字段回退，并由心跳测试验证。

### 19.6 最终验证

标准命令：

```bash
python -m pytest -q
```

结果：

```text
137 passed, 0 failed, 64 warnings
```

测试总数比升级前增加 5 项，来自 IntentParser 现代契约的参数化覆盖。

剩余 64 条均为非阻断弃用告警，主要包括：

1. Pydantic V2 不再推荐 `Field(..., env=...)` 和 class-based `Config`。
2. FastAPI 不再推荐 `@app.on_event`，应迁移到 lifespan。
3. LangChain 的内置 `Chroma` 已弃用，应迁移到 `langchain-chroma`。

这些告警不影响当前功能，但应作为后续依赖升级任务处理。

## 20. 2026-07-09 依赖弃用接口迁移

### 20.1 初始状态

旧测试基线升级完成后的结果：

```text
137 passed, 64 warnings
```

告警来源：

| 来源 | 数量 | 原因 |
|---|---:|---|
| Pydantic | 57 | `Field(env=...)` 和 class-based `Config` 已弃用 |
| FastAPI | 6 | `@app.on_event("startup"/"shutdown")` 已弃用 |
| LangChain Chroma | 1 | `langchain_community.vectorstores.Chroma` 已弃用 |

### 20.2 实施进度

| 任务 | 状态 | 结果 |
|---|---|---|
| 审查告警来源与依赖版本 | 已完成 | 确认三类告警均可独立迁移 |
| Pydantic Settings 迁移 | 已完成 | 使用 `SettingsConfigDict`，保留原环境变量命名 |
| Pydantic API 模型迁移 | 已完成 | 使用 `ConfigDict` 和 `model_dump()` |
| FastAPI lifespan 迁移 | 已完成 | 合并两个 startup 和一个 shutdown 处理器 |
| Chroma 包迁移 | 已完成 | 使用 `langchain-chroma==1.1.0` |
| 新增迁移回归测试 | 已完成 | Settings 环境变量 1 项，lifespan 行为 2 项 |
| 全量回归 | 已完成 | `140 passed, 0 warnings` |

### 20.3 Pydantic 迁移

`app/config.py`：

- 使用 `SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")`。
- 删除所有旧式 `Field(..., env="...")` 参数。
- Pydantic Settings 默认按字段名读取大小写不敏感的环境变量，因此现有
  `OPENAI_API_KEY`、`LLM_PROVIDER`、`SESSION_STORAGE`、`POSTGRES_PORT`
  等配置名称保持不变。
- 新增 `tests/test_config.py`，验证原环境变量名称仍然生效。

API 请求模型：

- `AgentRuleConfig` 和 `RpaPageContext` 改用 `ConfigDict(extra="allow")`。
- 路由中的 `.dict()` 全部改为 `.model_dump()`。

### 20.4 FastAPI lifespan 迁移

`app/main.py` 原先存在两个同名 `startup_event`：

1. 初始化并启动已配置的平台 chat manager。
2. 初始化 Agent engine，并检查 storage manager。
3. shutdown 时停止 chat manager。

现在统一进入一个 `@asynccontextmanager` lifespan：

```text
应用启动
  -> 构造平台配置
  -> 初始化/启动 chat manager
  -> 初始化 Agent engine
  -> 检查 storage manager
应用退出
  -> 停止 chat manager
```

新增 `tests/test_app_lifespan.py`，覆盖：

- 有平台配置时初始化并启动平台，退出时停止。
- 无平台配置时跳过平台启动，但仍执行退出清理。

### 20.5 Chroma 迁移

当前环境兼容版本：

```text
langchain-chroma=1.1.0
chromadb=1.5.1
langchain-core=1.2.14
numpy=2.1.3
```

变更：

- `requirements.txt` 增加 `langchain-chroma==1.1.0`。
- `app/rag/vector_store.py` 改为 `from langchain_chroma import Chroma`。
- 保留原有持久化目录、collection name、embedding function 和检索接口。
- 向量库、知识摄取和 workflow 风险策略相关 12 项测试通过。

### 20.6 最终验证

```bash
python -m pytest -q
```

```text
140 passed in 22.45s
0 failed
0 warnings
```

本阶段将测试数量从 137 增加到 140，并将告警数量从 64 降为 0。

## 21. 2026-07-09 客服模拟测试支持商品作用域

### 21.1 目标

客服工作台里的“模拟测试”不能只裸测当前平台知识库，还应能选择某个已导入或已抓取的商品，模拟真实买家围绕该商品提问。这样可以验证：

1. 商品信息是否按 `merchant_id + platform + shop_id + product_id` 正确进入智能客服上下文。
2. 商品推荐、价格、库存、类目、商品专属问答是否优先使用当前商品资料。
3. 拼多多等真实平台客服页和本地测试窗口是否共用同一套 `CustomerServiceWorkflow`。

### 21.2 已完成

1. `frontend/src/services/api.ts`
   - 新增 `ProductSummary`、`ProductListData` 类型。
   - 新增 `fetchProducts()`，读取 `/api/products`，支持 `merchant_id/platform/shop_id/limit/offset` 查询参数。

2. `frontend/src/components/CustomerServiceHub.tsx`
   - 模拟测试区域加载当前平台、当前店铺下的商品列表。
   - 新增模拟测试商品选择器：
     - 不限定商品：只按当前平台/店铺知识库回答。
     - 选择商品：把商品 ID、平台商品 ID、SKU、标题、类目、价格、库存写入 `page_context`。
   - `/api/chat/query` 调用现在可携带：

```json
{
  "page_context": {
    "platform": "pinduoduo",
    "shop_id": "shop-1",
    "product_id": "local-product-id",
    "platform_product_id": "pdd-goods-id",
    "sku": "sku-1",
    "title": "商品标题",
    "product_title": "商品标题",
    "category": "商品类目",
    "price": 88,
    "stock": 5,
    "source": "customer_service_simulation"
  }
}
```

### 21.3 当前效果

客服页模拟测试现在更接近真实平台消息：

```text
选择平台/店铺
  -> 选择某个商品
  -> 输入买家问题
  -> /api/chat/query
  -> CustomerServiceWorkflow
  -> 商品上下文匹配 + RAG 检索 + 证据来源返回
```

如果用户问“这个还有货吗”“多少钱”“适合什么场景”，工作流可以优先参考被选中的商品，而不是只从平台级知识库里猜。

### 21.4 验证结果

通过：

```bash
cd frontend
npm run build

python -m pytest tests\test_products.py tests\test_workflow_risk_strategy.py -q
python -m pytest -q
```

结果：

```text
frontend build: passed
tests/test_products.py + tests/test_workflow_risk_strategy.py: 34 passed
full pytest: 140 passed
```

### 21.5 后续待办

1. 模拟测试 UI 增加商品搜索，避免商品多时下拉列表太长。
2. 允许直接选择“当前平台页面里的商品卡片”，而不是只从本地商品库选择。
3. 结果区展示本次命中的商品字段，例如价格、库存、推荐理由。
4. 把模拟测试用例保存为测试集，后续批量评估 AI 回复质量。
5. 继续修复 `CustomerServiceHub.tsx` 中历史乱码文案，降低后续维护成本。
