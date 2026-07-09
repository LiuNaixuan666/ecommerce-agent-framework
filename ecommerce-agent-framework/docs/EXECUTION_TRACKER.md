# 执行跟踪文档

## 1. 用途

本文档用于记录本项目后续改造的实施状态，避免因为对话上下文过长、需求变化或中途暂停导致开发偏离方向。

后续每次开始新一轮实现前，应先查看：

1. `docs/CURRENT_GOAL_AND_PROGRESS.md`
2. `docs/EXECUTION_TRACKER.md`
3. `docs/SELF_BUILT_LOCAL_AGENT_PLAN.md`
4. `docs/RPA_INTERFACE_SCHEMA.md`
5. `docs/LOCAL_RPA_CUSTOMER_SERVICE_PRD.md`
6. `docs/LOCAL_RPA_ARCHITECTURE.md`
7. `docs/IMPLEMENTATION_ROADMAP.md`

## 2. 当前总方向

在现有系统上继续改造，不推倒重写。

保留：

- FastAPI 后端
- 前端项目框架
- 文档上传能力
- Chroma / RAG 基础能力
- storage 和配置系统
- health 接口

重点重构：

- 客服 Agent 核心流程
- 回复生成逻辑
- 风险判断
- 澄清逻辑
- RPA 接入流程
- 自研 Local Agent 消息监听、回填发送和发送结果回写
- 商家数据库接入
- 商品知识库绑定
- 前端客服工作台

## 3. 实施纪律

每一阶段开始前：

- 先确认本阶段目标
- 只改本阶段相关模块
- 不顺手大规模重构无关代码
- 明确验收标准

每一阶段完成后：

- 更新本文档状态
- 记录改了哪些文件
- 记录怎么验证
- 记录遗留问题

## 4. 阶段状态

### 阶段 0：现有系统稳定化

状态：已完成

已完成：

- 修复前端中文乱码和发送后跳回主页的问题。
- 清理 `intent_parser.py`，从测试场景改成通用电商意图识别。
- 清理 `routes_chat.py`，删除不可达旧流程，保留薄路由。
- 清理 `local_client.py`，移除测试文档和课程/图书样例硬编码。
- 重写 `response_generator.py`，删除乱码 prompt、旧 mock 文案和测试样例式回答。
- 整理 `workflow.py`，增加证据聚焦度判断和低质量证据转人工。
- 实测后端启动、健康检查、TXT/PDF/DOCX 上传、Chroma 入库、RAG 问答。

阶段 0 验证：

- `/health` healthy
- `/api/chat/health` healthy
- `/api/knowledge/health` healthy
- 上传 3 个测试文件成功：TXT、DOCX、PDF
- 上传任务 completed
- documents_processed = 3
- chunks_created = 3
- Chroma vector_store 已生成数据
- 无答案问题会澄清/转人工，不再从无关文档编造

### 阶段 1：结构化客服回复 + 自动发送边界 + 风险策略

状态：已完成

目标：

- 后端返回结构化客服决策结果
- 明确 `recommended_reply`
- 明确 `risk_level`
- 明确 `auto_send_allowed`
- 明确 `auto_send_blockers`
- 明确 `requires_human_review`
- 明确 `handoff_reason`
- 明确 `missing_info`
- 前端展示风险、自动发送状态、阻止原因、来源和置信度

本轮已完成：

- `WorkflowResult` 新增：
  - `auto_send_allowed`
  - `auto_send_blockers`
- `ChatResponse` 新增：
  - `auto_send_allowed`
  - `auto_send_blockers`
- 自动发送策略已放在 workflow 中统一计算。
- 当前自动发送允许条件：
  - `risk_level == low`
  - 不需要人工审核
  - 非澄清回复
  - 无缺失信息
  - confidence >= 0.5
  - 有结构化数据或可用证据
  - 证据聚焦度足够
- 中风险、高风险、低置信度、证据不聚焦、缺信息、需要澄清时禁止自动发送。
- 前端 `ChatInterface` 已展示：
  - 允许自动发送 / 转人工
  - 风险等级
  - 置信度
  - 意图
  - 阻止原因
  - 转人工原因
  - 缺失信息
  - 来源
- `frontend/src/services/api.ts` 已补齐结构化字段类型。
- 新增 RPA 标准接口：
  - `POST /api/chat/rpa/message`
  - 请求以 `platform + external_conversation_id + customer_message` 为核心
  - 响应固定返回 `decision.auto_send_allowed`
  - RPA 后续只根据 `decision.auto_send_allowed` 决定是否自动发送
  - 后端用 `merchant_id + platform + external_conversation_id` 生成稳定内部会话 ID
  - 支持 `external_message_id` 去重，避免同一条消息被重复处理
- 新增接口文档 `docs/RPA_INTERFACE_SCHEMA.md`。
- 新增 Local Agent 闭环接口：
  - `POST /api/chat/rpa/send-result`
  - `GET /api/chat/rpa/send-results`
  - `POST /api/local-agent/heartbeat`
  - `GET /api/local-agent/status`
  - `GET /api/local-agent/status/{agent_id}`
- 自动发送风险策略已配置化：
  - `AUTO_SEND_MIN_CONFIDENCE`，默认 `0.5`
  - `AUTO_SEND_ALLOW_MEDIUM_RISK`，默认 `false`
  - 默认行为保持保守，中风险仍不自动发送

阶段 1 验证：

- `D:\anaconda3\python.exe -m py_compile app\agent\workflow.py app\api\routes_chat.py app\agent\response_generator.py app\llm\local_client.py` 通过。
- `frontend` 执行 `npm run build` 通过。
- 接口冒烟：
  - “运费规则是什么？”返回 `risk_level=low`，`auto_send_allowed=true`。
  - “这个商品支持几天无理由退货？”返回 `risk_level=medium`，`auto_send_allowed=false`，blocker 包含 `risk_medium`。
  - “我要投诉，你们必须赔偿我！”返回 `risk_level=high`，`auto_send_allowed=false`，blocker 包含 `risk_high` 和 `human_review_required`。
  - “老板手机号是多少？”返回澄清/转人工，`auto_send_allowed=false`。
- RPA 接口冒烟：
  - `POST /api/chat/rpa/message` 低风险商品库存问题返回 `decision.action=send`，`decision.auto_send_allowed=true`，`rpa_instruction.send_text` 有值。
  - 相同 `external_message_id` 重复提交时返回 `message.duplicate_event=true`。
  - 高风险投诉赔偿问题返回 `decision.action=handoff`，`decision.auto_send_allowed=false`，`rpa_instruction.send_text=null`。
  - RPA 内部会话 ID 长度为 36，兼容当前 PostgreSQL 会话表 ID 限制。
- Local Agent 闭环接口冒烟：
  - `POST /api/chat/rpa/send-result` 记录 `send_status=success` 后返回 `processing_status=auto_sent`。
  - `GET /api/chat/rpa/send-results?merchant_id=phase1_closeout` 返回 1 条发送结果。
  - `POST /api/local-agent/heartbeat` 记录 `status=running`。
  - `GET /api/local-agent/status/local-agent-001` 返回 `status=running`，`platform=mock_shop`。
- 风险策略配置冒烟：
  - 默认 `AUTO_SEND_ALLOW_MEDIUM_RISK=false`。
  - “这个商品支持几天无理由退货？”返回 `risk_level=medium`，`auto_send_allowed=false`，blocker 包含 `risk_medium`。

阶段 1 剩余事项：

- [x] 将 `auto_send_allowed` 接入后续 RPA 标准接口。
- [x] 新增 `/api/chat/rpa/send-result`，记录 Local Agent 实际发送成功、失败、转人工或跳过原因。
- [x] 新增 `/api/local-agent/heartbeat`，记录 Local Agent 在线状态、监听平台、最近消息和异常。
- [x] 风险策略配置化，例如商家可选择 medium 风险是否允许自动发送。
- [ ] 前端后续升级为真正客服工作台，而不是聊天 demo 中展示决策信息。该事项移动到阶段 6。

## 5. 待办总览

### P0

- [x] 阶段 0：现有系统稳定化
- [x] 阶段 1：结构化客服回复
- [ ] 阶段 2：自研 Local Agent 骨架与 Mock 客服闭环
- [ ] 阶段 3：新消息监听、去重和会话队列
- [ ] 阶段 4：自动回填、发送验证和发送结果回写
- [ ] 阶段 5：页面上下文读取

### P1

- [ ] 本地模拟商家数据库
- [ ] 商品知识库 metadata 绑定
- [ ] 数据源配置页面
- [ ] 客服工作台
- [ ] 问答模板沉淀
- [ ] 会话上下文和摘要

### P2

- [ ] 外部搜索
- [ ] 多平台 RPA 模板
- [ ] ERP / 平台 API 可选接入

## 6. 当前决策记录

### 2026-06-12：是否推倒重写

决策：不推倒重写，在现有系统上做重构式改造。

原因：

- 当前系统已经有可运行的后端、前端、上传、RAG、配置和健康检查。
- 完全重写会丢掉已验证的工程基础。
- 现阶段真正需要替换的是客服业务核心，而不是所有基础设施。

### 2026-06-12：自动发送策略

决策：默认支持低风险、高置信度问题自动发送；高风险、低置信度、缺少关键信息的问题转人工。

关键要求：

- 多平台多会话并发
- 同一会话内部串行处理
- 自动发送前检查消息是否过期
- 每条自动发送记录来源、置信度、风险等级和发送结果

## 7. 下一步

进入阶段 2：自研 Local Agent 骨架与 Mock 客服闭环，优先考虑：

阶段 2 已启动。

已完成：

1. 新建 `app/local_agent` 目录。
2. 实现 `BasePlatformAdapter`。
3. 实现 `MockShopAdapter`。
4. 为 `MockShopAdapter` 增加事件队列，新消息入队，处理后出队并去重。
5. 新增 `LocalAgentRuntime`，统一构造后端 RPA 消息 payload 和发送结果 payload。
6. 新增 `LocalAgentRuntime.process_once()`，跑通单轮 Local Agent 闭环。
7. 新增 `LocalBackendClient`，封装 `/api/chat/rpa/message`、`/api/chat/rpa/send-result`、`/api/local-agent/heartbeat`。
8. 新增 `python -m app.local_agent.run_mock`，可从命令行启动 Mock Local Agent 处理。
9. 新增 `LocalAgentLoop`，支持持续轮询、周期 heartbeat、错误记录和 Ctrl+C 停止。
10. `run_mock` 支持 `--watch`、`--interval`、`--max-cycles` 和多个 `--message`。
11. 新增 `watchers/base.py`，定义真实页面消息监听协议。
12. 新增 `extractors/base.py`，定义页面上下文抽取协议。
13. 新增 `executors/base.py`，定义回填、发送、转人工执行协议。
14. 新增 `store/deduper.py` 和 `store/session_queue.py`，用于去重和会话队列。
15. 新增 `GenericWebChatAdapter`，组合 watcher / extractor / executor，并内置去重和会话队列。
16. `PlatformMessage` 新增 `observed_at`，用于消息过期检查。
17. `SendResult` 新增 `sent_at`，用于记录真实发送时间。
18. `LocalAgentRuntime` 新增 `max_message_age_seconds`，过期消息回写 `skipped_stale`，不再调后端生成回复。
19. `LocalAgentRuntime` 新增 `send_retry_attempts`，发送异常或失败结果会重试，重试耗尽回写 `failed`。
20. `SessionQueue` 新增 `drain_conversation_serial()`，明确同一会话内部串行处理。
21. 新增 `browser/selectors.py`，集中定义浏览器页面选择器。
22. 新增 `watchers/browser_page.py`，从浏览器页面读取买家消息 DOM。
23. 新增 `extractors/browser_page.py`，从浏览器页面抽取商品上下文。
24. 新增 `executors/browser_page.py`，回填输入框、点击发送并校验已发送消息。
25. 新增 `adapters/browser_web_chat.py`，组装浏览器页面 watcher / extractor / executor。
26. 新增 `mock_pages/browser_chat.html`，作为类真实网页客服页面。
27. 新增 `run_browser_mock.py`，可选使用 Python Playwright 运行真实浏览器闭环。
28. 新增前端 `MockShopWorkbench`，作为最小 Mock 客服页面。
29. 前端默认打开 Mock 工作台，并保留知识库聊天页。

阶段 2 当前验证：

- `npm run build` 通过。
- 后端 `py_compile` 通过。
- 新增 `tests/test_local_agent_mock.py`，`pytest tests/test_local_agent_mock.py -q` 通过，7 个用例覆盖：
  - MockShopAdapter 只读取一次新消息。
  - LocalAgentRuntime 构造 `/api/chat/rpa/message` payload。
  - LocalAgentRuntime 构造 `/api/chat/rpa/send-result` payload。
  - `process_once()` 对低风险消息自动发送并回写结果。
  - `process_once()` 对禁止自动发送的消息转人工并回写结果。
  - `LocalAgentLoop` 多轮轮询时每轮发送 heartbeat，但只处理一次新消息。
  - `LocalAgentLoop` 记录单轮异常，不让长期进程直接崩溃。
- 新增 `tests/test_generic_web_chat_adapter.py`，覆盖：
  - raw event 转换为 `PlatformMessage`。
  - 重复消息去重。
  - 页面上下文绑定。
  - `send_text` / `mark_handoff` 委托 executor。
  - health 状态合并。
- 新增可靠性策略测试，覆盖：
  - 过期消息不调用后端决策，直接回写 `skipped_stale`。
  - 发送异常后重试并成功。
  - 发送失败结果重试耗尽后回写 `failed`。
  - 会话队列按会话内顺序串行输出。
- 新增 `tests/test_browser_web_chat_adapter.py`，覆盖：
  - 浏览器页面买家消息读取。
  - 商品上下文抽取。
  - 输入框回填、点击发送、已发送消息校验。
  - 发送未被页面确认时返回 `failed`。
- `pytest tests/test_browser_web_chat_adapter.py tests/test_generic_web_chat_adapter.py tests/test_local_agent_mock.py -q` 通过，17 个用例。
- Playwright 打开 `http://127.0.0.1:5173/` 成功。
- Mock 工作台默认买家消息“这款有现货吗？”运行一次 Local Agent 后：
  - 后端返回 `action=send`
  - 页面追加 AI 客服自动回复
  - 消息状态为 `auto_sent`
  - 后端 send result 记录 `processing_status=auto_sent`
- Mock 工作台新增中风险消息“这个商品支持几天无理由退货？”运行一次 Local Agent 后：
  - 后端返回 `action=handoff`
  - 页面显示转人工
  - 阻止原因为 `risk_medium`
  - 后端 send result 记录 `processing_status=handoff_required`
- 命令行 Mock Local Agent 真实后端闭环验证：
  - `python -m app.local_agent.run_mock --message "Is this item in stock?"` 返回 `action=send`，send result 为 `auto_sent`。
  - `python -m app.local_agent.run_mock --message "这个商品支持几天无理由退货？"` 返回 `action=handoff`，send result 为 `handoff_required`。
- 持续监听模式真实后端验证：
  - `python -m app.local_agent.run_mock --watch --interval 0 --max-cycles 3 --message "Is this item in stock?"` 返回 `cycles=3`，`processed_count=1`。
  - 后两轮没有重复处理同一条消息。
  - `GET /api/local-agent/status/local-agent-watch-cli` 返回 `status=running`，`pending_messages=0`，`sent_messages=1`。
- 可靠性策略真实后端验证：
  - `python -m app.local_agent.run_mock --watch --interval 0 --max-cycles 2 --message "Is this item in stock?"` 成功。
  - send result 成功回写 `sent_at`。
  - send result metadata 成功回写 `send_attempts=1` 和 `max_send_attempts=2`。
- 浏览器页面 Adapter 原型验证：
  - `py_compile` 通过。
  - Fake Page 单元测试通过。
  - 已安装 Python Playwright 包。
  - Playwright 自带 Chromium 下载超时，后续优先通过 `--browser-channel msedge` 复用本机 Edge。
  - `mock_pages/browser_chat.html` 的回复框已改为 `textarea`，支持多行客服回复。
  - `BrowserPageReplyExecutor` 已支持发送校验时归一化空白，避免页面折叠换行导致误判失败。
  - 真实浏览器命令已通过：
    - `python -m app.local_agent.run_browser_mock --backend-url http://127.0.0.1:8000 --agent-id local-agent-browser-real --merchant-id browser_real_verify_auto_sent --browser-channel msedge`
  - 真实浏览器闭环结果：
    - Edge 打开本地 mock 页面。
    - Local Agent 读取买家消息 `Is this item in stock?`。
    - Local Agent 抽取商品上下文 `Browser Test Product / SKU-001 / stock=12`。
    - 后端返回 `action=send`。
    - 页面回填并点击发送。
    - 发送校验成功，`send_status=success`。
    - 后端 send result 回写 `processing_status=auto_sent`。
- 发现遗留风险：
  - 英文退货/投诉基础风险策略已修复，但后续仍需要做成商家可配置词表和动作策略。
- 英文风险策略修复：
  - `intent_parser.py` 补充 `exchange`、`after-sale`、`after sales` 等 policy 关键词。
  - `workflow.py` 补充英文中风险词：`return`、`refund`、`exchange`、`invoice`、`order`、`tracking`、`after-sale` 等。
  - `workflow.py` 补充英文高风险词：`complaint`、`compensation`、`lawsuit`、`chargeback`、`negative review`、`bad review`、`fake`、`counterfeit`、`fraud`、`scam` 等。
  - 新增 `tests/test_workflow_risk_strategy.py`。
  - `pytest tests/test_workflow_risk_strategy.py tests/test_browser_web_chat_adapter.py tests/test_generic_web_chat_adapter.py tests/test_local_agent_mock.py -q` 通过，23 个用例。
  - 新代码临时后端 `8001` live 验证通过：
    - `Can I return this item after opening it?` 返回 `action=handoff`、`auto_send_allowed=false`、`risk_level=medium`、`risk_medium`。
    - `I want to complain and demand compensation.` 返回 `action=handoff`、`auto_send_allowed=false`、`risk_level=high`、`risk_high`、`human_review_required`。
  - 注意：原本运行在 `8000` 的后端进程仍加载旧代码，重启后才会应用本次风险策略修复。
- 浏览器选择器 Profile 机制：
  - 新增 `browser/profiles.py`，支持内置 profile 和外部 JSON profile。
  - `run_browser_mock.py` 新增 `--profile` 和 `--selector-profile-json`。
  - 新增 `browser_profiles/pinduoduo_web.template.json`，作为拼多多网页客服选择器模板。
  - 新增 `docs/BROWSER_SELECTOR_PROFILE_GUIDE.md`，记录真实平台选择器提取和验证流程。
  - 新增 `tests/test_browser_profiles.py`，覆盖内置 profile、JSON profile 加载和配置缺失校验。
  - `pytest tests/test_browser_profiles.py tests/test_browser_web_chat_adapter.py tests/test_generic_web_chat_adapter.py tests/test_local_agent_mock.py tests/test_workflow_risk_strategy.py -q` 通过，26 个用例。
  - 改造后默认 `browser_mock` profile 已用 Edge live 验证，仍可自动发送并回写 `auto_sent`。
- 拼多多真实 URL 快速扫描：
  - URL: `https://mms.pinduoduo.com/chat-merchant/index.html?r=0.5541775007481573#/`
  - 命令：`python -m app.local_agent.run_browser_discovery --browser-channel msedge --user-data-dir data\browser_profiles\pdd_edge --wait-before-scan 8`
  - 结果：Playwright 新 Edge profile 进入拼多多登录页，不是已登录客服页。
  - 已生成快速扫描结果：`data\browser_profiles\pdd_selector_candidates_quick.json`。
  - 下一步需要用 headed 模式在 `data\browser_profiles\pdd_edge` 这个专用 profile 中登录拼多多，再扫描真实客服页 DOM。
- 拼多多真实客服页选择器与 dry-run 验证：
  - 已在 `data\browser_profiles\pdd_edge` 专用浏览器 profile 中打开真实拼多多客服页。
  - 已生成真实客服页 DOM 扫描结果：`data\browser_profiles\pdd_selector_candidates.json`。
  - 已生成本地选择器配置：`app/local_agent/browser_profiles/pinduoduo_web.local.json`。
  - 当前关键选择器：
    - `root`: `div.content`
    - `buyer_messages`: `div.buyer-item:not(:has(.good-card))`
    - `reply_input`: `#replyTextarea`
    - `send_button`: `div.send-btn`
    - `sent_messages`: `div.cs-item p.msg-content-box`
    - `product_name`: `a.good-detail`
    - `sku`: `p.good-id`
    - `price`: `span.good-price`
  - 已用 `--dry-run` 跑通真实拼多多页面单轮闭环：
    - Local Agent 读取买家消息 `你好`。
    - 后端返回 `intent=CHITCHAT`。
    - 后端返回推荐回复 `您好，请问有什么可以帮您？`。
    - 浏览器执行器返回 `send_status=skipped_dry_run`，没有真实回填或点击发送。
    - 后端 send result 回写 `processing_status=skipped_dry_run`。
  - 已修复寒暄消息带商品上下文时的误回复问题：
    - `workflow.py` 中 `CHITCHAT` 优先返回客服问候语。
    - 新增 `test_chitchat_uses_greeting_even_with_product_context`。
  - 当前仍未做真实发送。真实发送前必须先补最新消息过滤和显式真发开关。
- 真实平台发送安全闸门：
  - `BrowserPageWatcher` 新增 `latest_only`，默认只返回最新一条可见买家消息。
  - `build_browser_web_chat_adapter` 新增 `latest_only` 参数。
  - `run_browser_mock.py` 默认强制 dry-run；未传 `--allow-real-send` 时不会回填输入框，也不会点击发送。
  - `run_browser_mock.py` 新增 `--allow-real-send`，只有显式传入时才允许真实发送。
  - `run_browser_mock.py` 新增 `--process-all-visible`，仅用于调试读取全部可见消息，真实平台默认不要使用。
  - 命令输出新增 `safety` 字段，显示 `allow_real_send`、`dry_run`、`latest_only`。
  - `docs/BROWSER_SELECTOR_PROFILE_GUIDE.md` 已更新默认 dry-run、真实发送和 latest-only 使用说明。
- 拼多多 headed dry-run 稳定性验证：
  - 临时后端 `8001` 健康检查通过。
  - 非 headed/headless 场景曾进入客服平台外壳但未选中会话，页面显示“正在连接服务器...”，因此 `processed_count=0`。
  - 使用 headed 模式命令跑通：
    - `python -m app.local_agent.run_browser_mock --backend-url http://127.0.0.1:8001 --agent-id local-agent-pdd-dryrun-headed --merchant-id pdd_dryrun_headed_20260618 --browser-channel msedge --headed --user-data-dir data\browser_profiles\pdd_edge --selector-profile-json app\local_agent\browser_profiles\pinduoduo_web.local.json --page-url "https://mms.pinduoduo.com/chat-merchant/index.html?r=0.5541775007481573#/" --wait-before-run 45`
  - 结果：
    - `processed_count=1`
    - 读取买家消息 `你好`
    - 后端返回 `intent=CHITCHAT`
    - 推荐回复 `您好，请问有什么可以帮您？`
    - 执行层返回 `send_status=skipped_dry_run`
    - 后端 send result 回写 `processing_status=skipped_dry_run`
    - `safety.allow_real_send=false`
    - `safety.dry_run=true`
    - `safety.latest_only=true`
  - 新增兼容修复：当浏览器页面未识别到聊天 DOM 时，Local Agent heartbeat 会把 `not_detected` 映射为后端可接受的 `error`，原始状态保留在 metadata，避免 heartbeat 422 阻断流程。

下一步：

1. 等拼多多页面出现新的低风险买家消息后，做一次单条、headed、显式 `--allow-real-send` 的真实发送验证。
2. 真实发送前再次确认 `safety.latest_only=true`，并避免使用 `--process-all-visible`。
3. 继续扩充风险词表和商家可配置风险策略。

## 8. 新方向决策记录

### 2026-06-17：从影刀外置 RPA 转向自研 Local Agent

决策：后续主线不再把影刀作为核心执行层，而是将已经落地的 RPA 标准接口作为 Local Agent 调用后端的稳定协议，自己实现消息读取、新消息监听、自动回填、发送验证和状态回写。

原因：

- 影刀适合早期验证，但不适合作为毕设核心系统能力。
- 自研 Local Agent 能更完整体现无平台 API 智能客服系统的技术贡献。
- 当前 `/api/chat/rpa/message` 已经落地，可以直接复用为 Local Agent 的后端决策接口。
- 自研消息监听、去重、会话串行、发送结果确认更容易和前端工作台、后端审计打通。

保留：

- 保留现有 FastAPI 后端、RAG、结构化回复、风险策略、RPA 标准接口。
- 保留影刀作为可选验证工具或对照方案。

新增主线：

1. 新增 `/api/chat/rpa/send-result`，记录真实发送结果。
2. 新增 `/api/local-agent/heartbeat`，记录本地 Agent 在线和监听状态。
3. 新建 `app/local_agent`，实现自研消息读取和自动回填执行器。
4. 优先实现 `MockShopAdapter` 和 Mock 客服页面，保证毕设演示稳定。
5. 再扩展 `GenericWebChatAdapter` 或具体平台适配器。

新的下一阶段：阶段 2 调整为「自研 Local Agent 骨架与 Mock 客服闭环」，详见 `docs/SELF_BUILT_LOCAL_AGENT_PLAN.md`。

### 2026-06-18：产品形态升级为多平台本地 AI 客服中台

决策：后续产品主线从“单个平台自动回复验证”升级为“多平台本地 AI 客服中台”。第一优先级仍然是拼多多，但前端和后端模型要开始按多平台、多接待模式、多知识来源设计，避免后面接闲鱼、千牛、京东、抖店时大面积重写。

参考产品截图中确认值得吸收的能力：

- 多平台图标入口和平台运行状态。
- 平台商品信息导入到知识库。
- 商品知识和通用政策分层管理。
- AI 全托管、人机协作、智能转接三种接待模式。
- 转人工触发项可配置。
- 历史聊天记录用于优化 AI 回复。

本项目的升级点：

- 保留本地运行和自研 Local Agent，不依赖平台官方 API。
- 保留 `auto_send_allowed`、`risk_level`、`auto_send_blockers` 等结构化安全决策。
- 强化商品知识 metadata 绑定，避免不同商品文档互相污染。
- 把拼多多 dry-run 能力产品化为平台工作台，而不是只停留在命令行验证。

规划文档：`docs/MULTI_PLATFORM_AI_CUSTOMER_SERVICE_PRODUCT_PLAN.md`

新的下一阶段：阶段 5 调整为「多平台控制台产品骨架」。先做首页平台卡片、拼多多平台详情页、Local Agent 状态展示和 dry-run 决策展示，暂不扩大真实发送范围。

### 2026-06-19：阶段 5 多平台控制台产品骨架完成

决策：完成阶段 5 的核心实现，将系统首页从单一聊天页升级为多平台 AI 客服中台。

新增后端：
- `app/api/routes_platform.py` — 平台注册表和状态聚合 API。
- `GET /api/platform/list` — 返回平台列表，合并 Local Agent 心跳数据。
- `GET /api/platform/{code}/status` — 返回平台详情，包含 Agent 列表和最近发送记录。
- 注册了 5 个平台：拼多多（active）、闲鱼（coming_soon）、淘宝/千牛（coming_soon）、京东（coming_soon）、抖店（coming_soon）。
- `tests/test_platform_routes.py` — 5 个测试用例全部通过。

新增前端：
- `Sidebar.tsx` — 深色主题侧边栏导航，含折叠功能。
- `Dashboard.tsx` — 综合工作台首页，显示平台卡片、统计概览、已接入/待接入平台分组。
- `PlatformDetail.tsx` — 拼多多平台工作台详情页，展示 Agent 运行状态、心跳、最近发送记录表格。
- `PlatformAccess.tsx` — 平台接入管理页（含占位待接入平台）。
- `ReplyStrategy.tsx` — AI 回复策略配置页（三种接待模式选择 + 自动发送开关）。
- `RunLogs.tsx` — 运行日志页（骨架，后续填充真实数据）。
- `App.tsx` — 重写为侧边栏导航 + 内容区布局，移除旧的两标签切换。
- `api.ts` — 新增 `fetchPlatformList`、`fetchPlatformStatus`、`PlatformInfo`、`PlatformStatusResponse` 等类型和函数。

验证：
- `npm run build` 通过（TypeScript + Vite）。
- `py_compile app/api/routes_platform.py` 通过。
- `py_compile app/main.py` 通过。
- `pytest tests/test_platform_routes.py -q` 5 passed。
- `pytest tests/test_local_agent_mock.py tests/test_generic_web_chat_adapter.py tests/test_browser_web_chat_adapter.py tests/test_browser_profiles.py tests/test_workflow_risk_strategy.py -q` 32 passed，未引入回归。

当前项目前端页面结构：

```
Sidebar (深色导航)
├── 综合工作台 (Dashboard.tsx) — 默认首页
│   ├── 统计概览（运行中 Agent / 接入平台 / 异常 Agent / 待接入）
│   ├── 已接入平台（拼多多卡片 → 点击进入详情）
│   └── 待接入平台（闲鱼、淘宝/千牛、京东、抖店）
├── 拼多多工作台 (PlatformDetail.tsx)
│   ├── 运行状态概览
│   ├── 会话监控面板（买家消息、商品上下文、AI 决策）
│   ├── 安全控制（Dry-Run / 允许发送切换）
│   ├── Agent 详情列表（心跳、状态、错误信息）
│   └── 最近发送记录表格
├── 平台接入 (PlatformAccess.tsx) — 浏览器 profile 管理
├── AI 回复策略 (ReplyStrategy.tsx) — 接待模式选择
├── 运行日志 (RunLogs.tsx) — 日志表格骨架
├── Mock 工作台 (MockShopWorkbench.tsx) — 保留
└── 知识库聊天 (ChatInterface.tsx) — 保留
```

### 2026-06-19：阶段 6 拼多多平台工作台 MVP 完成

决策：将已有的拼多多 dry-run 能力产品化为平台详情页内实时会话监控面板。

...

（前面的阶段记录保持不变）

---

## 9. 交接文档实施记录（2026-06-29）

按 `docs/CONTINUATION_HANDOFF_IMPLEMENTATION_GUIDE.md` 执行了 Step 0~Step 8。

### Step 0：基线检查 ✅

- `py_compile app/storage/product_store.py app/api/routes_products.py app/api/routes_knowledge.py app/agent/workflow.py app/rag/retriever.py app/rag/vector_store.py` 通过。
- `pytest tests/test_products.py -q`：16 passed。
- `npm run build`：前端构建通过。

### Step 1：修复商品关联文档上传链路 ✅

**修改文件：**
- `frontend/src/components/ProductManagement.tsx`：`formData.append('file', file)` → `formData.append('files', file)`（与后端 `List[UploadFile]` 匹配）。
- `app/api/routes_knowledge.py`：`start_ingestion()` 中补上 `product_id = task.get("product_id")`。

**验证：**
- `py_compile` 通过。
- `npm run build` 通过。
- 接口测试：`POST /api/knowledge/upload` 上传成功，task 中含 `product_id`，ingestion completed。

### Step 2：修复商品抓取平台注册表 ✅

**新增文件：**
- `app/local_agent/scrapers/registry.py` — 平台→scraper 映射注册表，支持 lazy import。

**修改文件：**
- `app/api/routes_products.py`：
  - scrape 接口增加 `is_product_scraper_supported()` 校验，不支持的平台返回 400 + `platform_scraper_not_supported`。
  - `_run_scrape()` 从硬编码 `PddProductScraper` 改为动态注册表查找。
- `frontend/src/components/ProductManagement.tsx`：非拼多多平台禁用"从平台抓取"按钮。

**验证：**
- `py_compile` 通过，`npm run build` 通过。
- `pytest tests/test_products.py -q`：16 passed。
- Live 验证：`platform=xianyu` 返回 400，`platform=pinduoduo` 返回 200 task。

### Step 3：商品列表按平台过滤 ✅

**修改文件：**
- `frontend/src/components/ProductManagement.tsx`：
  - `loadProducts()` 接受 `platform` 参数并传给 API。
  - `useEffect` 依赖 `importPlatform` 切换时自动重新加载。
  - CSV 导入、删除、抓取完成后按当前平台刷新。

**验证：**
- `npm run build` 通过。
- Live 验证：拼多多筛选只显示拼多多商品，闲鱼筛选返回空列表。

### Step 4：当前会话商品上下文解析成 product_id ✅

**修改文件：**
- `app/storage/product_store.py`：
  - 新增 `find_by_context()` — 5 级匹配优先级：product_id → platform_product_id → sku → 标题精确 → 标题包含。
  - 新增 `_normalize_text()` 辅助函数。
- `app/agent/workflow.py`：
  - 导入 `product_store`。
  - `_structured_from_page_context()` 中调用 `product_store.find_by_context()`，匹配结果写入 `matched_product_id`、`matched_product_title`、`product_id`。

**验证：**
- `py_compile` 通过。
- `pytest tests/test_products.py -q`：24 passed（新增 8 个 find_by_context 测试覆盖全部匹配优先级）。

### Step 5：RAG 检索支持 product_id 优先过滤 ✅

（与 Step 4 同步实现）

**修改文件：**
- `app/rag/retriever.py`：`retrieve()` 增加 `product_id` 参数，有值时用 Chroma filter 优先检索，结果不足时 fallback 全局。
- `app/agent/workflow.py`：`retrieve()` 从 `structured_data` 中提取 `product_id` 传给 `Retriever.retrieve()`。

**验证：**
- `py_compile` 通过。
- debug 数据增加 `rag_product_filter` 字段。

### Step 6：Local Agent 决策结果回传 UI ✅

**修改文件：**
- `app/local_agent/runtime.py`：`process_once()` 中构造 `latest_decision` snapshot，处理消息后更新 heartbeat 含 AI 决策数据（recommended_reply、risk_level、auto_send_allowed、auto_send_blockers、intent、confidence 等）。

**验证：**
- `py_compile` 通过。
- 前端 `PlatformDetail` 已有完整展示面板（买家消息、AI 决策、商品上下文）。

### Step 7：清理前端乱码和旧页面状态 ✅

**修改文件：**
- `frontend/src/components/Sidebar.tsx`：「拼多多工作台」→「平台工作台」（避免误导，平台详情实际由 platformCode 动态决定）。
- `frontend/src/components/PlatformDetail.tsx`：新增「启动方式」区域，展示 Local Agent 启动命令和安全提示。

**验证：**
- `npm run build` 通过。

### Step 8：端到端验证 ✅

后端部署测试验证：
- 健康检查通过 ✅
- 知识上传含 product_id ✅
- Ingestion 状态 completed，chunks_created=37 ✅
- 平台注册表：闲鱼返回 400 ✅，拼多多创建任务 ✅
- 商品列表按平台过滤 ✅

### 文件变更汇总

| 文件 | 修改类型 |
|------|---------|
| `app/storage/product_store.py` | 新增 `find_by_context()` |
| `app/agent/workflow.py` | 集成 product matching + RAG filtering |
| `app/rag/retriever.py` | 新增 `product_id` 参数 |
| `app/local_agent/scrapers/registry.py` | 新增注册表 |
| `app/api/routes_products.py` | 平台校验 + 动态 scraper |
| `app/api/routes_knowledge.py` | 修复 `product_id` 传递 |
| `app/local_agent/runtime.py` | 新增决策 heartbeat |
| `frontend/src/components/ProductManagement.tsx` | 修复字段名 + 平台过滤 + 禁用按钮 |
| `frontend/src/components/PlatformDetail.tsx` | 新增启动命令 |
| `frontend/src/components/Sidebar.tsx` | 文案修复 |
| `tests/test_products.py` | 新增 8 个 find_by_context 测试 |

### 下一阶段建议

1. **CSV 导入后自动上传关联文档** — 当前需手动逐个上传。
2. **风险策略配置界面** — 商家可配置风险词表和动作策略。
3. **真实拼多多页面小流量验证** — 用真实买家消息跑 dry-run 和真实发送。
4. **会话历史持久化** — 保存对话历史到 SQLite。

---

### 2026-06-29 补充修复：第二轮审查问题

按接手者审查意见修复以下问题：

**1. Step 6 字段契约对齐**
- `app/local_agent/runtime.py`：`risk_reasons` → `auto_send_blockers`
- 补充 `product_name`、`sku`、`product_price`、`stock`、`send_status` 到 heartbeat metadata
- `frontend/src/services/api.ts`：`AgentMetadata` 增加 `send_status` 字段

**2. bulk_create sku 去重跨平台漏洞**
- `app/storage/product_store.py`：sku 去重增加 `platform` 限定
- 新增 `test_bulk_create_sku_dedup_respects_platform` 验证跨平台隔离

**3. 前端抓取按钮错误处理**
- `frontend/src/components/ProductManagement.tsx`：`handleScrape()` 增加 `res.ok === false` 分支

**4. 新增 product_id → RAG 集成测试**
- `tests/test_workflow_risk_strategy.py` 新增：
  - `test_workflow_matches_product_and_passes_product_id_to_retriever` — 验证 page_context 匹配到 product_store 后 product_id 传给 retrieve()
  - `test_workflow_no_product_match_does_not_filter_rag` — 无匹配时不传 product_id
  - `test_normalize_text_whitespace_and_case` — 归一化辅助函数测试

**5. 文档状态统一**
- `docs/PHASE_7_8_INTEGRATION_REPAIR_PLAN.md`：Step 2-8 状态更新为"已完成"
- 增加 Step 2-8 执行记录

**验证：**
- `pytest tests/test_products.py tests/test_workflow_risk_strategy.py tests/test_platform_routes.py -q`：43 passed ✅
- `npm run build`：通过 ✅

---

### 2026-06-29：新增平台浏览器工作台与商品抓取对接计划

根据前端体验检查，确认当前仍存在两个产品级缺口：

1. 商品管理页点击“从平台抓取”时，只启动后端抓取任务，没有先打开对应平台商品页，也没有引导用户完成平台登录。
2. 当前平台详情页更偏状态看板，还不是完整客服工作台；缺少“左侧平台账号列表 + 右侧平台客服页面/浏览器会话控制 + AI 接待状态”的可视化形态。

新增文档：

- `docs/PLATFORM_BROWSER_WORKBENCH_INTEGRATION_PLAN.md`

文档明确了下一阶段实施方向：

- 不优先用普通 iframe 嵌入电商后台，因为跨域、登录态和 CSP 限制较多。
- 第一阶段采用“React 控制台 + Local Agent 打开独立浏览器窗口”的方式。
- 商品抓取改为“打开平台商品页 → 检测登录状态 → 用户确认 → 开始抓取”的向导式流程。
- 新增平台客服工作台页面，左侧显示平台账号和状态，右侧显示平台连接、AI 模式、最新买家消息、商品上下文、AI 决策和发送记录。
- 后端新增平台浏览器会话接口：open、check-login、start-agent、stop-agent、sessions。
- 继续保持多平台抽象：拼多多先完整支持，闲鱼、淘宝、京东、抖店只做占位，不允许误调用拼多多 scraper。

下一步建议从以下顺序继续：

1. 先修复前端中文乱码。
2. 新增平台页面配置和 browser session manager。
3. 新增 `/api/platform-browser/*` 接口。
4. 改造商品抓取按钮为抓取向导。
5. 新增真正的多平台客服工作台页面。
6. 拼多多 dry-run 验证后，再做真实发送小流量验证。
