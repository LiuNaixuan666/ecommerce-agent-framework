# 2026-07-06 对话实现与修改汇总

本文档记录本次对话中围绕“拼多多商品抓取 + 本地多平台 AI 客服工作台”完成的实现、修复、当前状态和待办事项。后续开发应先阅读本文，再阅读 `2026-07-06_CUSTOMER_SERVICE_HUB_IMPLEMENTATION_PLAN.md`。

## 1. 当前目标

系统目标是做一个无官方 API 依赖的本地电商 AI 客服平台：

1. 使用本地浏览器/Edge 登录电商平台。
2. 通过 Playwright/RPA 读取平台客服页、商品页 DOM。
3. 本地后端根据商品知识库、对话上下文和风险规则生成 AI 回复。
4. 前端客服工作台集中展示多平台账号、红点提醒、待人工消息、AI 推荐回复、历史会话、知识学习和模拟测试。
5. 支持先从拼多多跑通 MVP，后续扩展闲鱼、淘宝/千牛、京东、抖店等平台。

## 2. 已完成改动

### 2.1 拼多多商品抓取修复

相关文件：

- `app/local_agent/scrapers/pdd_product_scraper.py`
- `app/api/routes_products.py`
- `frontend/src/components/ProductScrapeWizard.tsx`
- `app/local_agent/browser_session_manager.py`
- `app/api/routes_platform_browser.py`

完成内容：

1. 修复商品列表抓取不到的问题。
   - 抓取器不再只依赖旧版 `TB_` 虚拟表结构。
   - 新增对当前拼多多商品列表常见 `table/tbody/tr/td` DOM 的解析。
   - 根据表头字段识别商品信息、价格、库存、销量等列。
   - 尝试提取商品标题、商品 ID、SKU、图片、详情链接。

2. 商品抓取任务改为复用已打开的浏览器会话。
   - 后端抓取逻辑通过平台浏览器线程执行。
   - 避免抓取时重新打开/关闭浏览器，导致登录态丢失或窗口被抢占。
   - 详情页抓取也进入同一个 Playwright worker 流程。

3. 修复弹出平台窗口被用户关闭后卡死的问题。
   - `check_login` 会检测 page/session 是否还活着。
   - 如果页面关闭或浏览器断连，会重新打开会话。
   - 前端增加“重新打开平台页面”能力。
   - `/api/platform-browser/open` 遇到 session error 时返回 HTTP 500，前端能明确显示失败。

4. 商品抓取向导现状。
   - 正常流程仍是：打开平台商品页 -> 登录 -> 检测登录 -> 扫描列表 -> 选择商品 -> 逐个详情页补 description -> 导入商品库。
   - 列表 DOM 解析已增强。
   - 后续仍需继续加页面滚动、分页、虚拟列表和详情字段容错。

### 2.2 开发端口与代理调整

相关文件：

- `frontend/vite.config.js`

完成内容：

1. 前端 Vite `/api` 代理临时指向 `http://localhost:8001`。
2. 原因是本地 `8000` 端口出现 Windows 残留/僵尸监听，短期用 `8001` 保证开发继续。
3. 当前验证：
   - 前端：`http://127.0.0.1:5173` 返回 200。
   - 后端：`http://127.0.0.1:8001/health` 返回 healthy。

注意：

- 这是当前机器上的临时开发状态。
- 后续整理启动脚本时，需要统一端口策略：要么恢复 8000，要么正式改为 8001 并同步文档、脚本和环境变量。

### 2.3 拼多多客服页监听与 AI 接待

相关文件：

- `app/local_agent/browser/profiles.py`
- `app/local_agent/watchers/browser_page.py`
- `app/api/routes_platform_browser.py`
- `app/local_agent/runtime.py`
- `app/local_agent/http_client.py`
- `frontend/src/components/PlatformBrowserWorkbench.tsx`

完成内容：

1. 新增拼多多网页客服 profile。
   - 内置 `pinduoduo_web_profile()`。
   - 使用 sentinel selector：
     - `__pdd_auto_buyer_messages__`
     - `__pdd_auto_reply_input__`
     - `__pdd_auto_send_button__`
     - `__pdd_auto_sent_messages__`

2. 新增拼多多客服页消息识别逻辑。
   - `BrowserPageWatcher` 可对拼多多页面执行专用 JS。
   - 能识别买家消息、过滤导航/规则/底部文案噪声。
   - 通过消息文本、位置和 DOM 背景等启发式判断买家气泡。

3. 新增后端浏览器 Agent runner。
   - `/api/platform-browser/start-agent` 可启动后台循环。
   - `/api/platform-browser/stop-agent` 可停止后台循环。
   - runner 会：
     - 打开/复用平台客服页；
     - 读取新买家消息；
     - 调用 `/api/chat/rpa/message`；
     - 根据 AI 决策执行 dry-run、handoff 或发送动作；
     - 回写 `/api/chat/rpa/send-result`；
     - 发送 `/api/local-agent/heartbeat`。

4. AI 推荐回复不再很快消失。
   - `LocalAgentRuntime` 保存 `_last_decision_snapshot`。
   - 心跳刷新时会合并上一次 AI 决策，不会被空心跳覆盖。

5. 前端原工作台做过初步增强。
   - 平台列表红点提醒。
   - 最近处理记录。
   - 区分 chat/products 页面 session，避免商品页被误认为客服页。

### 2.4 新增聚合客服工作台

相关文件：

- `frontend/src/components/CustomerServiceHub.tsx`
- `frontend/src/App.tsx`

完成内容：

1. 新增 `CustomerServiceHub` 组件，替代原 `客服工作台` 页面入口。
2. 页面布局：
   - 左侧：平台账号列表、登录状态、监听状态、红点/待人工提示。
   - 顶部：当前平台、登录状态、监听状态、接待模式、打开客服页、检测登录、启动/停止 AI。
   - 左中：待人工处理队列。
   - 中间：当前/历史会话列表与消息详情。
   - 右侧：固定 AI 推荐回复、最新买家消息、风险、置信度、阻止自动发送原因。
   - 底部 Tab：
     - 转人工规则；
     - 对话学习；
     - 模拟测试；
     - 处理记录。

3. 已接入的后端能力：
   - 平台列表：`/api/platform/list`
   - 浏览器 session：`/api/platform-browser/sessions`
   - Agent 心跳：`/api/local-agent/status`
   - 平台处理记录：`/api/platform/{platform}/status`
   - 本地会话列表：`/api/chat/conversations`
   - 会话历史：`/api/chat/conversations/{conversation_id}/history`
   - 知识库上传：`/api/knowledge/upload`
   - 模拟测试：`/api/chat/query`

4. 当前已支持的交互：
   - 打开客服页。
   - 检测登录。
   - 启动/停止 AI 监听。
   - 设置当前接待模式：只记录不发送、半托管填入、低风险自动发送。
   - 查看待人工消息。
   - 本地标记待人工消息已处理。
   - 人工处理后点击“转回 AI 接待”。
   - 查看历史会话。
   - 查看 AI 推荐回复。
   - 复制 AI 推荐回复。
   - 从历史会话生成知识草稿。
   - 上传优质对话到知识库。
   - 模拟测试 AI 回答质量。

注意：

- 当前“转人工规则”是前端 MVP，可选但尚未持久化，也尚未真正接入后端决策规则。
- 当前“标记已处理”是前端本地状态，刷新后会丢失。
- 当前“复制回复”和“人工发送后转回 AI”已经具备演示价值，但后续要与真实平台输入框填入、状态流转打通。

### 2.5 RPA 发送结果与会话列表增强

相关文件：

- `app/local_agent/runtime.py`
- `app/api/routes_chat.py`
- `frontend/src/services/api.ts`

完成内容：

1. RPA `send-result` payload 现在带 `customer_message`。
   - 之前处理记录可能只有 AI 回复或发送状态，前端无法展示买家原话。
   - 现在可以在“最近处理记录”和“待人工队列”里显示买家消息。

2. `RpaSendResultRequest` 增加 `customer_message` 字段。

3. `/api/chat/conversations` 返回更多信息：
   - `platform`
   - `customer_id`
   - `customer_name`
   - `external_conversation_id`
   - `last_send_status`
   - `processing_status`

4. 前端 `RpaSendResultPayload` 类型同步增加：
   - `customer_message`
   - `skipped_dry_run` 状态。

## 3. 当前上下文记忆与历史消息机制

当前系统已经有“本地会话记忆”，但不是完整的平台历史自动同步。

### 3.1 当前会话存储

买家消息进入 `/api/chat/rpa/message` 后：

1. 后端根据 `merchant_id + platform + external_conversation_id` 生成稳定本地 conversation_id。
2. 买家消息写入 `storage_manager`。
3. AI 回复也写入同一个 conversation。
4. 下一次 AI 决策会读取最近历史消息作为上下文。

### 3.2 存储位置

取决于当前配置：

1. Redis/PostgreSQL 可用时，走持久化存储。
2. 否则走内存 fallback，服务重启会丢失。

当前 `/health` 显示 storage healthy，说明本机当前至少有一个存储后端可用。

### 3.3 尚未完成的平台历史同步

当前不会自动把拼多多页面里“以前已经存在的完整聊天记录”全部导入。

现在能看到的是：

1. 系统运行期间 RPA 捕捉过的消息。
2. 系统通过 `/api/chat/rpa/message` 处理过的消息。
3. 人工上传/学习过的优质对话文档。

后续需要实现：

1. 从平台客服页主动读取当前会话历史。
2. 支持按会话、按时间范围、按商品抓取历史。
3. 将抓取到的历史对话进入“清洗 -> 编辑 -> 审核 -> 导入知识库”流程。

## 4. 已验证事项

本次完成后执行过：

```bash
python -m py_compile app/local_agent/runtime.py app/api/routes_chat.py
npm run build
```

验证结果：

1. Python 编译通过。
2. 前端 TypeScript + Vite 构建通过。
3. 前端 `http://127.0.0.1:5173` 可访问。
4. 后端 `http://127.0.0.1:8001/health` 返回 healthy。

## 5. 当前待办事项

### P0：继续保证拼多多 MVP 可跑通

1. 商品列表抓取继续加强：
   - 虚拟列表滚动；
   - 分页；
   - 商品详情页 description 容错；
   - 失败重试；
   - 抓取诊断日志。

2. 客服页 DOM 识别继续加强：
   - 减少误识别规则文案、系统提示、订单区内容；
   - 区分买家消息和商家/机器人消息；
   - 识别当前选中会话；
   - 识别未读会话红点。

3. 统一端口和启动脚本：
   - 解决 8000/8001 临时切换；
   - 写清楚后端启动命令；
   - 写清楚前端代理配置。

### P1：客服工作台从 MVP 变成可用产品

1. 转人工规则持久化。
2. 将规则真正接入 `workflow.py` 决策。
3. 待人工队列后端持久化。
4. 人工处理后状态流转：
   - 待人工；
   - 人工处理中；
   - 已处理；
   - 转回 AI；
   - 已关闭。

5. AI 推荐回复操作：
   - 复制；
   - 填入平台输入框；
   - 发送；
   - 标记人工发送；
   - 拒绝并修改；
   - 修改后学习。

### P1：历史对话学习闭环

1. 平台历史对话读取。
2. 对话清洗。
3. 问答对生成。
4. 人工编辑确认。
5. 导入知识库。
6. 记录来源和版本。
7. 支持上传优质对话 TXT/CSV/Excel。

### P2：多平台扩展

1. 抽象平台 profile：
   - 拼多多；
   - 闲鱼；
   - 淘宝/千牛；
   - 京东；
   - 抖店。

2. 每个平台需要独立配置：
   - 登录页；
   - 客服页；
   - 商品页；
   - 买家消息 selector；
   - 输入框 selector；
   - 发送按钮 selector；
   - 会话列表 selector；
   - 未读红点 selector。

3. 工作台左侧平台红点应来自真实未读/待人工状态，而不是仅从当前 Agent 心跳推断。

### P2：模拟测试与质量评估

1. 支持输入商品上下文。
2. 支持选择知识库范围。
3. 支持批量测试问题集。
4. 对 AI 回复打分：
   - 是否准确；
   - 是否引用知识；
   - 是否触发转人工；
   - 是否存在敏感词；
   - 是否过度承诺。

5. 支持把优质模拟回复一键加入知识库。

## 6. 继续开发建议

建议下一步按照以下顺序继续：

1. 已完成：规则持久化接口、前端规则读取/保存、`workflow.py` 规则接入。
2. 下一步：完成待人工队列后端持久化接口。
3. 做平台历史对话抓取和学习导入。
4. 再回头加强拼多多商品详情抓取。
5. 最后扩展闲鱼等第二个平台。
