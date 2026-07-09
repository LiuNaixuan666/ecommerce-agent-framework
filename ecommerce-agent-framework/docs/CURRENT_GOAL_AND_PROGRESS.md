# 当前目标与推进记录

## 当前主线

自研 Local Agent，而不是把影刀作为核心执行层。产品形态从单一客服/RAG 页面升级为「多平台本地 AI 客服中台」，第一优先级主攻拼多多，后续扩展闲鱼、千牛、京东、抖店等平台。

当前系统定位：

```text
本地电商智能客服后端
  + 自研 Local Agent
  + 多平台客服控制台
  + 拼多多真实页面 dry-run
  + 商品知识导入与平台 Adapter 扩展
```

## 当前阶段

阶段 5：多平台控制台产品骨架。

当前规划文档：`docs/MULTI_PLATFORM_AI_CUSTOMER_SERVICE_PRODUCT_PLAN.md`

## 已完成

- 阶段 0：现有系统稳定化。
- 阶段 1：结构化客服回复字段。
- 阶段 1：自动发送边界。
- 阶段 1：风险策略基础版。
- 阶段 1：风险策略配置化：

```text
AUTO_SEND_MIN_CONFIDENCE=0.5
AUTO_SEND_ALLOW_MEDIUM_RISK=false
```

默认仍然保守，中风险不自动发送。
- 阶段 1：RPA/Local Agent 标准消息入口：

```text
POST /api/chat/rpa/message
```

- 阶段 1 收尾：Local Agent 闭环接口：

```text
POST /api/chat/rpa/send-result
GET  /api/chat/rpa/send-results
POST /api/local-agent/heartbeat
GET  /api/local-agent/status
GET  /api/local-agent/status/{agent_id}
```

该接口已经返回：

- `recommended_reply`
- `decision.auto_send_allowed`
- `decision.action`
- `decision.risk_level`
- `decision.auto_send_blockers`
- `rpa_instruction.send_text`

## 当前待做

### P0 — 已完成（2026-06-19）

1. ✅ 前端首页改成多平台客服控制台，展示拼多多、闲鱼、千牛、京东、抖店等平台卡片。
2. ✅ 拼多多卡片接入已有 Local Agent 状态，展示登录/运行/dry-run/最近消息/最近回复结果。
3. ✅ 新增拼多多平台详情页，展示读取到的买家消息、商品上下文、AI 推荐回复、风险等级、阻断原因。
4. ✅ 知识库入口开始区分商品知识、店铺通用政策、问答模板，为后续商品绑定做铺垫。
5. ✅ 暂不扩大真实发送范围，继续默认 dry-run，真实发送仍必须显式开启。

### P0 当前待做（阶段 6 — 已完成 2026-06-19）

1. ✅ 后端扩展 Heartbeat 模型，Agent 可上报最新买家消息、选择器 Profile、当前页面 URL。
2. ✅ 新增 `POST /api/local-agent/seed-demo` 开发用数据注入端点。
3. ✅ 前端 PlatformDetail 新增「会话监控」面板：买家消息、商品上下文、AI 决策（推荐回复、风险等级、自动发送状态、阻断原因）。
4. ✅ 前端新增「安全控制」区域：Dry-Run / 允许真实发送切换。
5. ✅ 前端自动轮询刷新（每 5 秒拉取最新数据）。
6. ✅ 前端 Agent 详情卡片增加监控字段展示。

## 交接文档实施（2026-06-29）

已完成 `docs/CONTINUATION_HANDOFF_IMPLEMENTATION_GUIDE.md` 中 Step 0~Step 8。

### 已修复的关键链路

| 链路 | 状态 |
|------|------|
| 商品文档上传字段名不一致 | ✅ 修复 |
| 手动启动 ingestion 时 product_id 丢失 | ✅ 修复 |
| 商品抓取平台硬编码 | ✅ 修复（注册表） |
| 商品列表前端没有按平台过滤 | ✅ 修复 |
| RAG 没有按 product_id 过滤 | ✅ 修复 |
| 会话商品上下文匹配 product_id | ✅ 修复 |
| Local Agent 决策结果回传 UI | ✅ 修复 |
| 页面文案清理和启动命令提示 | ✅ 修复 |

### 最关键的链路：商品文档绑定 → product_id 匹配 → RAG 按 product_id 检索

这个链路已经修通。

### 下一步

1. **CSV 导入后自动上传关联文档** — 当前需手动逐个上传。
2. **风险策略配置界面** — 商家可配置风险词表和动作策略。
3. **真实拼多多页面小流量验证** — 用真实买家消息跑 dry-run 和 --allow-real-send。
4. **问答模板沉淀** — 人工处理后沉淀为标准回答。

### 下一阶段 P0

1. 将真实 Local Agent 的 `latest_buyer_message` / `selector_profile` 等字段通过 heartbeat metadata 上报到后端。
2. 平台接入页真正连接浏览器 Profile 和选择器配置。
3. 商品信息导入页面与商品知识绑定。

```text
新消息 -> 后端决策 -> 自动回填/转人工 -> 发送结果回写
```

### 已完成的阶段 2 子项

- 新建 `app/local_agent`。
- 实现 `BasePlatformAdapter`。
- 实现 `MockShopAdapter`。
- 实现 `LocalAgentRuntime` payload 构造骨架。
- 实现 `LocalAgentRuntime.process_once()`，跑通单轮处理闭环。
- 新增 `LocalBackendClient`，封装 Local Agent 调用本地 FastAPI 的 HTTP 请求。
- 新增 `python -m app.local_agent.run_mock`，可从命令行启动一次 Mock Local Agent 处理。
- `MockShopAdapter` 已加入事件队列，新增消息入队，处理后出队并去重。
- 新增 `LocalAgentLoop`，支持持续轮询、周期 heartbeat、错误记录和 Ctrl+C 停止。
- `python -m app.local_agent.run_mock` 已支持：
  - `--watch`
  - `--interval`
  - `--max-cycles`
  - 多个 `--message`
- 新增 `MockShopWorkbench` 最小 Mock 客服页面。
- Mock 工作台已验证：
  - 低风险商品库存问题自动发送。
  - 中风险退货问题转人工。
  - 发送结果能回写后端。
- 新增 `tests/test_local_agent_mock.py`，覆盖 MockShopAdapter 去重读取、runtime payload 构造、低风险自动发送、中风险转人工。
- 命令行真实后端闭环已验证：
  - `python -m app.local_agent.run_mock --message "Is this item in stock?"` 返回 `action=send` 并回写 `processing_status=auto_sent`。
  - `python -m app.local_agent.run_mock --message "这个商品支持几天无理由退货？"` 返回 `action=handoff` 并回写 `processing_status=handoff_required`。
- 持续监听模式已验证：
  - `python -m app.local_agent.run_mock --watch --interval 0 --max-cycles 3 --message "Is this item in stock?"`
  - 3 轮循环只处理 1 条新消息，后续轮次不重复发送。
  - `/api/local-agent/status/local-agent-watch-cli` 可查询 heartbeat，`pending_messages=0`，`sent_messages=1`。
- 真实平台 Adapter 基础协议已完成：
  - 新增 `watchers/base.py`，定义 `RawMessageEvent` 和 `MessageWatcher`。
  - 新增 `extractors/base.py`，定义 `PageContextExtractor`。
  - 新增 `executors/base.py`，定义 `ReplyExecutor`。
  - 新增 `store/deduper.py` 和 `store/session_queue.py`。
  - 新增 `GenericWebChatAdapter`，组合 watcher / extractor / executor，并内置去重和会话队列。
  - 新增 `tests/test_generic_web_chat_adapter.py`，覆盖读取、去重、上下文绑定、发送委托和 health 合并。
- Local Agent 可靠性策略已补齐：
  - `PlatformMessage` 新增 `observed_at`，用于消息过期判断。
  - `SendResult` 新增 `sent_at`，用于记录真实发送时间。
  - `LocalAgentRuntime` 支持 `max_message_age_seconds`，过期消息不调后端决策，直接回写 `skipped_stale`。
  - `LocalAgentRuntime` 支持 `send_retry_attempts`，发送异常或失败结果会重试。
  - 重试耗尽后回写 `failed`，并记录 `send_attempts` / `max_send_attempts`。
  - `SessionQueue` 新增 `drain_conversation_serial()`，明确同一会话内按顺序处理。
  - 真实后端验证：`run_mock --watch --max-cycles 2` 成功回写 `sent_at` 和发送尝试次数。
- 阶段 4 浏览器页面 Adapter 原型已完成：
  - 新增 `browser/selectors.py`，集中定义页面选择器。
  - 新增 `watchers/browser_page.py`，从浏览器页面读取买家消息 DOM。
  - 新增 `extractors/browser_page.py`，从浏览器页面抽取商品上下文。
  - 新增 `executors/browser_page.py`，回填输入框、点击发送并校验已发送消息。
  - 新增 `adapters/browser_web_chat.py`，组装浏览器页面 watcher / extractor / executor。
  - 新增 `mock_pages/browser_chat.html`，提供类真实网页客服页面。
  - 新增 `run_browser_mock.py`，可选使用 Python Playwright 运行真实浏览器闭环。
  - 新增 `tests/test_browser_web_chat_adapter.py`，覆盖读消息、抽上下文、回填发送、发送校验失败。
  - 已安装 Python Playwright 包。
  - Playwright 自带 Chromium 下载超时，已改为支持 `--browser-channel` 复用本机 Edge/Chrome。
  - `mock_pages/browser_chat.html` 的回复框已改为 `textarea`，支持多行客服回复。
  - `BrowserPageReplyExecutor` 已支持发送校验时归一化空白，避免页面折叠换行导致误判失败。
  - 真实浏览器闭环已通过：
    - `python -m app.local_agent.run_browser_mock --backend-url http://127.0.0.1:8000 --agent-id local-agent-browser-real --merchant-id browser_real_verify_auto_sent --browser-channel msedge`
    - 返回 `send_status=success`。
    - 后端回写 `processing_status=auto_sent`。
    - metadata 包含 `verification=sent_text_found`、`send_attempts=1`、`max_send_attempts=2`。
- 浏览器选择器 Profile 机制已完成：
  - 新增 `browser/profiles.py`，支持内置 profile 和外部 JSON profile。
  - `run_browser_mock.py` 新增 `--profile` 和 `--selector-profile-json`。
  - 新增 `browser_profiles/pinduoduo_web.template.json`，作为拼多多网页客服选择器模板。
  - 新增 `docs/BROWSER_SELECTOR_PROFILE_GUIDE.md`，记录真实平台选择器提取和验证流程。
  - 新增 `tests/test_browser_profiles.py`，覆盖内置 profile、JSON profile 加载和配置缺失校验。
  - 改造后默认 `browser_mock` profile 已用 Edge live 验证，仍可自动发送并回写 `auto_sent`。
- 拼多多真实 URL 快速扫描已执行：
  - URL: `https://mms.pinduoduo.com/chat-merchant/index.html?r=0.5541775007481573#/`
  - Playwright 新 Edge profile 当前进入登录页，不是已登录客服页。
  - 已生成 `data\browser_profiles\pdd_selector_candidates_quick.json`。
  - 下一步需要用 headed 模式在 `data\browser_profiles\pdd_edge` 专用 profile 中登录拼多多，再扫描真实客服页 DOM。
- 拼多多真实客服页选择器已完成第一轮 dry-run 验证：
  - 使用 `data\browser_profiles\pdd_edge` 专用浏览器 profile 打开真实拼多多客服页。
  - 成功扫描真实客服页 DOM，并生成 `data\browser_profiles\pdd_selector_candidates.json`。
  - 已生成本地选择器配置：`app/local_agent/browser_profiles/pinduoduo_web.local.json`。
  - 当前关键选择器：
    - 根节点：`div.content`
    - 买家消息：`div.buyer-item:not(:has(.good-card))`
    - 回复输入框：`#replyTextarea`
    - 发送按钮：`div.send-btn`
    - 已发送消息：`div.cs-item p.msg-content-box`
    - 商品名称：`a.good-detail`
    - 商品编号：`p.good-id`
    - 商品价格：`span.good-price`
  - 已用 `--dry-run` 验证真实拼多多页面：
    - Local Agent 能读到买家消息 `你好`。
    - 后端识别为 `CHITCHAT`。
    - 后端推荐回复 `您好，请问有什么可以帮您？`。
    - 执行结果为 `skipped_dry_run`，没有回填输入框、没有点击发送。
    - 后端 send result 回写 `processing_status=skipped_dry_run`。
  - 已修复寒暄场景在带商品上下文时误走商品回复的问题：
    - `CHITCHAT` 固定优先返回客服问候语。
    - 新增测试覆盖：`test_chitchat_uses_greeting_even_with_product_context`。

### 遗留风险

- 英文退货/投诉基础风险策略已修复，但后续仍需要做成商家可配置词表和动作策略。

### 已修复风险

- 英文 `return` / `refund` / `exchange` 会被识别为中风险，默认不自动发送。
- 英文 `complain` / `compensation` / `bad review` / `fraud` / `fake` 等会被识别为高风险，强制转人工。
- 新增 `tests/test_workflow_risk_strategy.py`，覆盖英文退货、退款、换货、投诉、赔偿、欺诈风险。
- 新代码临时后端 `8001` live 验证通过：
  - `Can I return this item after opening it?` 返回 `action=handoff`、`auto_send_allowed=false`、`risk_level=medium`、`risk_medium`。
  - `I want to complain and demand compensation.` 返回 `action=handoff`、`auto_send_allowed=false`、`risk_level=high`、`risk_high`、`human_review_required`。

### P1

1. 本地模拟商家数据库。
2. 商品知识库 metadata 绑定。
3. 客服工作台。

### 下一步 P0

1. 已补 `latest-only` 机制，浏览器命令默认只处理最新一条可见买家消息，避免把历史消息重新处理一遍。
2. 已补真实发送显式开关，`run_browser_mock.py` 默认强制 dry-run；只有传入 `--allow-real-send` 才允许回填输入框并点击发送。
3. 已补 `--process-all-visible` 调试开关；真实平台不要使用这个开关，除非是在专门调试历史消息读取。
4. 拼多多页面 dry-run 稳定性验证：
   - 非 headed/headless 场景偶尔只进入客服平台外壳，页面显示“正在连接服务器...”，没有选中会话，因此 `processed_count=0`。
   - 使用 `--headed --wait-before-run 45` 后成功进入真实会话。
   - 读取最新买家消息 `你好`。
   - 后端返回 `intent=CHITCHAT`，推荐回复 `您好，请问有什么可以帮您？`。
   - 执行层返回 `send_status=skipped_dry_run`，未回填、未点击发送。
   - 命令输出 `safety.allow_real_send=false`、`safety.dry_run=true`、`safety.latest_only=true`。
5. 下一步：确认有一条新的低风险买家消息后，再考虑一次显式 `--allow-real-send` 的真实发送验证。

## 当前验收标准

阶段 2 完成时，必须满足：

- 启动一个 Local Agent 进程。
- 后端能看到 Agent heartbeat。
- Mock 页面新买家消息能被 Agent 读取。
- Agent 能调用 `/api/chat/rpa/message`。
- 低风险回复能自动回填到 Mock 页面。
- 高风险或低置信度问题不会自动发送。
- Agent 能调用 `/api/chat/rpa/send-result` 回写结果。

## 不做事项

当前暂不做：

- 真实拼多多完整适配。
- OCR。
- Windows UI Automation。
- 云端账号体系。
- 多商家 SaaS 登录注册。
- 素材库、视频发送、智能转接。

这些放在 Mock 闭环之后。

## 开工前必读

每次继续开发前，先看：

1. `docs/CURRENT_GOAL_AND_PROGRESS.md`
2. `docs/EXECUTION_TRACKER.md`
3. `docs/SELF_BUILT_LOCAL_AGENT_PLAN.md`
4. `docs/RPA_INTERFACE_SCHEMA.md`
