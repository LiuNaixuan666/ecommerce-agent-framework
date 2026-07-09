# 平台浏览器工作台与商品抓取对接实施计划

## 1. 文档目的

这份文档用于继续实现“本地多平台 AI 客服中台”的平台浏览器对接能力。

当前系统已经具备：

- 后端 FastAPI 服务。
- 知识库上传与 RAG 检索。
- 商品库、CSV 导入、商品文档绑定。
- 拼多多商品抓取的后端任务接口。
- Local Agent 读取页面消息、调用 AI、根据风险策略决定自动发送或转人工。
- 多平台首页、平台详情页、商品管理页的基础前端骨架。

但目前还有两个核心产品缺口：

1. 商品管理页点击“从平台抓取”时，只是调用后端抓取任务，没有把用户带到对应平台商品管理页面，也没有处理未登录状态。
2. 还没有一个真正的“多平台客服工作台”：左侧显示已登录/已接入的平台账号，右侧显示对应平台客服页面，用户既能看到真实平台页面，也能手动接管回复。

本阶段目标是把这两个缺口补齐，使系统从“后台接口能跑”升级为“商家可以可视化使用的平台工作台”。

## 2. 产品目标

### 2.1 商品抓取目标

商家在商品管理页选择平台后，点击“从平台抓取”，系统应进入清晰的抓取流程：

1. 检查当前平台是否支持商品抓取。
2. 检查该平台是否已有可用浏览器登录态。
3. 如果没有登录态，打开对应平台登录页或商家后台页，让商家先登录。
4. 登录完成后进入平台商品管理页。
5. 商家确认当前页面已经进入商品列表。
6. 用户点击“开始抓取”。
7. 后端 Local Agent / Scraper 从该页面读取商品列表。
8. 抓取结果写入本地商品库。
9. 前端商品列表刷新，只显示当前平台商品。

### 2.2 客服工作台目标

系统需要新增一个“平台客服工作台”页面，参考竞品形态：

- 左侧：平台账号列表。
- 右侧：对应平台真实客服页面。
- 顶部或侧边：AI 接待模式、运行状态、未读消息、转人工队列。
- 用户可以在真实客服页面里手动回复。
- Local Agent 可以在同一个页面上监听买家消息、生成回复、回填输入框、自动发送或转人工。

第一阶段只完整支持拼多多。其他平台只做占位，不假装已经支持。

## 3. 当前问题判断

### 3.1 商品抓取按钮的问题

当前商品管理页里的“从平台抓取”按钮主要做了：

- 调用 `POST /api/products/scrape`。
- 后端直接启动 headless/headed 浏览器抓取。
- 前端轮询 `/api/products/scrape/{task_id}/status`。

问题是：

- 用户看不到真实平台页面。
- 用户不知道当前是否已经登录。
- 如果没有登录态，抓取任务会失败，但用户不知道该怎么处理。
- 用户无法选择“全部获取 / 部分获取”。
- 用户无法确认当前抓取的是哪个店铺、哪个平台页面。

所以应把“从平台抓取”改成一个引导式流程，而不是直接启动后台任务。

### 3.2 客服工作台的问题

当前 `PlatformDetail.tsx` 更像“平台状态看板”，展示 Agent 心跳、最近消息和发送记录。

它还不是一个真正的“客服工作台”，因为：

- 右侧没有嵌入或打开对应平台客服页面。
- 左侧没有平台账号/店铺列表。
- 用户不能在同一个页面中手动操作真实平台客服窗口。
- Local Agent 和可视化页面之间仍然偏命令行驱动。

后续应新增或重构一个页面，例如：

- `PlatformBrowserWorkbench.tsx`
- 或把 `PlatformDetail.tsx` 拆成“状态面板 + 浏览器工作台”两个区域。

## 4. 关键技术路线

### 4.1 不使用 iframe 直接嵌入平台网页

不要优先尝试用普通前端 iframe 嵌入拼多多商家后台。

原因：

- 大多数电商后台会设置 `X-Frame-Options` 或 CSP，禁止被第三方页面 iframe。
- 登录态、验证码、扫码登录、跨域 Cookie 都会出现限制。
- 即使 iframe 能打开，前端也不能跨域读取 DOM，也无法直接控制输入框和发送按钮。

因此推荐路线是：

1. 系统前端展示“工作台壳”和状态信息。
2. Local Agent 使用 Playwright / 浏览器持久化 profile 打开真实平台页面。
3. 前端通过后端接口控制 Local Agent 打开页面、切换页面、启动监听、暂停监听。
4. 如果需要把真实页面“显示在系统里”，第一阶段采用“独立浏览器窗口 + 前端状态同步”，而不是强行 iframe。
5. 后续如果要做真正内嵌窗口，可考虑 Electron / WebView2 桌面壳。

### 4.2 第一阶段推荐形态

第一阶段先做“可视化控制台 + 独立浏览器窗口”：

- 前端页面左侧显示平台账号。
- 用户点击“打开拼多多客服页”。
- 后端调用 Local Agent 打开带登录态的浏览器窗口。
- 用户在浏览器窗口中完成登录。
- 前端显示该 Agent 的状态：未登录、已登录、监听中、异常、转人工。
- Local Agent 对浏览器窗口进行 DOM 监听和自动回复。

这比强行把平台网页嵌进 React 页面更稳定，也更符合本地 RPA/浏览器自动化方案。

### 4.3 第二阶段桌面化形态

如果后续希望像竞品那样把平台页面显示在同一个应用窗口中，可以做 Electron 桌面壳：

- 左侧是 React 控制台。
- 中间或右侧是 WebView2/Electron BrowserView 显示真实平台页面。
- 主进程持有浏览器会话。
- Local Agent 通过 Playwright CDP 或 Electron API 控制页面。

但这是后续阶段，不建议当前立刻做。

## 5. 页面设计

### 5.1 商品管理页改造

当前商品管理页继续保留：

- 平台选择。
- CSV 导入。
- 商品列表。
- 商品文档绑定。

需要新增“平台抓取向导”。

点击“从平台抓取”后，不应直接启动抓取任务，而是打开一个弹窗或抽屉：

#### 弹窗标题

`从拼多多抓取商品`

#### 弹窗内容

显示以下状态：

- 当前平台：拼多多。
- 浏览器 Profile：`data/browser_profiles/pdd_edge`。
- 登录状态：未知 / 未登录 / 已登录。
- 目标页面：拼多多商品管理页。
- 支持模式：
  - 全部抓取。
  - 当前页抓取。
  - 勾选商品抓取。

#### 操作按钮

1. `打开平台商品页`
   - 调用后端接口，让 Local Agent 打开拼多多商品管理页。
   - 如果未登录，用户在弹出的浏览器窗口里完成登录。

2. `检测登录状态`
   - 后端读取当前浏览器页面 URL、标题、关键 DOM。
   - 如果还在登录页，返回 `login_required`。
   - 如果已经在商品管理页，返回 `ready`。

3. `开始抓取`
   - 只有状态为 `ready` 时可点击。
   - 调用 `POST /api/products/scrape`。

4. `查看抓取进度`
   - 轮询任务状态。

### 5.2 多平台客服工作台页面

新增页面建议命名：

- 前端组件：`PlatformBrowserWorkbench.tsx`
- 导航名称：`客服工作台`
- 路由状态：`platform-workbench`

页面布局：

```text
┌────────────────────────────────────────────────────────────┐
│ 顶部：本地 AI 客服工作台 / 当前模式 / 全局运行状态             │
├───────────────┬────────────────────────────────────────────┤
│ 左侧平台列表   │ 右侧平台工作区                                │
│               │                                            │
│ 拼多多 店铺A   │ ① 平台页面控制区                              │
│ 运行中 AI      │ - 打开客服页                                  │
│ 未读 3         │ - 检测登录                                    │
│               │ - 启动监听 / 暂停监听                          │
│ 闲鱼 未接入    │ - Dry-run / 自动发送开关                        │
│               │                                            │
│ 淘宝 未接入    │ ② 实时接待状态                                │
│               │ - 最新买家消息                                │
│               │ - 当前商品上下文                              │
│               │ - AI 推荐回复                                 │
│               │ - 风险等级 / 是否自动发送                      │
│               │                                            │
│               │ ③ 最近发送记录 / 转人工队列                    │
└───────────────┴────────────────────────────────────────────┘
```

重要说明：

- 右侧第一阶段不强行内嵌真实平台页面。
- 真实平台页面由 Local Agent 打开的独立浏览器窗口承载。
- 前端显示“当前窗口标题、URL、登录状态、监听状态”，并提供操作按钮。
- 用户手动回复时，直接在独立浏览器窗口中操作。

### 5.3 左侧平台列表

每个平台账号显示：

- 平台图标。
- 平台名称。
- 店铺名或账号名。
- 登录状态：
  - 未打开。
  - 需登录。
  - 已登录。
  - 监听中。
  - 异常。
- AI 模式：
  - 全托管。
  - 半托管。
  - 只推荐不发送。
- 未读数。
- 转人工数。

第一版数据来源：

- `/api/platform/list`
- `/api/platform/{platform_code}/status`
- Local Agent heartbeat。

### 5.4 右侧平台工作区

当用户选择拼多多时，右侧显示：

1. 平台连接状态。
2. 打开平台按钮：
   - `打开拼多多客服页`
   - `打开拼多多商品页`
3. 登录状态检测结果。
4. Agent 控制：
   - 启动监听。
   - 暂停监听。
   - Dry-run。
   - 允许自动发送。
5. 最近买家消息。
6. 当前商品上下文。
7. AI 决策。
8. 最近发送记录。
9. 转人工队列。

## 6. 后端接口设计

### 6.1 平台浏览器会话接口

新增路由文件：

`app/api/routes_platform_browser.py`

建议接口前缀：

`/api/platform-browser`

### 6.2 打开平台页面

```http
POST /api/platform-browser/open
```

请求：

```json
{
  "platform": "pinduoduo",
  "page_type": "chat",
  "merchant_id": "default",
  "shop_id": "default",
  "profile_id": "pdd_edge",
  "headed": true
}
```

`page_type` 可选：

- `chat`：客服聊天页面。
- `products`：商品管理页面。
- `orders`：订单页面，后续扩展。

返回：

```json
{
  "status": "opened",
  "platform": "pinduoduo",
  "page_type": "chat",
  "agent_id": "pinduoduo-default",
  "profile_dir": "data/browser_profiles/pdd_edge",
  "target_url": "https://mms.pinduoduo.com/chat-merchant/index.html"
}
```

职责：

- 根据平台和页面类型查 URL。
- 使用持久化浏览器 profile 打开页面。
- 不立即抓取、不立即发送。
- 只负责把浏览器窗口打开到正确位置。

### 6.3 检测登录状态

```http
POST /api/platform-browser/check-login
```

请求：

```json
{
  "platform": "pinduoduo",
  "page_type": "chat",
  "profile_id": "pdd_edge"
}
```

返回：

```json
{
  "platform": "pinduoduo",
  "logged_in": true,
  "status": "ready",
  "current_url": "https://mms.pinduoduo.com/chat-merchant/index.html",
  "page_title": "拼多多商家客服",
  "reason": null
}
```

未登录返回：

```json
{
  "platform": "pinduoduo",
  "logged_in": false,
  "status": "login_required",
  "current_url": "https://mms.pinduoduo.com/login",
  "page_title": "登录",
  "reason": "当前页面仍在登录页或未检测到客服工作台 DOM"
}
```

### 6.4 启动监听

```http
POST /api/platform-browser/start-agent
```

请求：

```json
{
  "platform": "pinduoduo",
  "page_type": "chat",
  "merchant_id": "default",
  "shop_id": "default",
  "profile_id": "pdd_edge",
  "mode": "dry_run",
  "interval_seconds": 10
}
```

`mode` 可选：

- `dry_run`：只生成回复和记录，不回填，不发送。
- `assist`：生成回复并回填输入框，但不点击发送。
- `auto`：低风险自动发送，高风险转人工。

返回：

```json
{
  "status": "started",
  "agent_id": "pinduoduo-default-chat",
  "platform": "pinduoduo",
  "mode": "dry_run"
}
```

### 6.5 暂停监听

```http
POST /api/platform-browser/stop-agent
```

请求：

```json
{
  "agent_id": "pinduoduo-default-chat"
}
```

返回：

```json
{
  "status": "stopped",
  "agent_id": "pinduoduo-default-chat"
}
```

### 6.6 获取浏览器会话状态

```http
GET /api/platform-browser/sessions
```

返回：

```json
{
  "sessions": [
    {
      "agent_id": "pinduoduo-default-chat",
      "platform": "pinduoduo",
      "page_type": "chat",
      "status": "running",
      "logged_in": true,
      "current_url": "https://mms.pinduoduo.com/chat-merchant/index.html",
      "page_title": "拼多多商家客服",
      "last_heartbeat_at": "2026-06-29T01:30:00",
      "latest_buyer_message": "这个有货吗",
      "latest_decision": {
        "recommended_reply": "亲，这款目前有货，可以正常拍下。",
        "auto_send_allowed": true,
        "risk_level": "low",
        "auto_send_blockers": []
      }
    }
  ]
}
```

## 7. 平台配置设计

新增配置文件：

`app/local_agent/platforms/platform_registry.py`

或 JSON 配置：

`app/local_agent/platforms/platforms.json`

建议结构：

```json
{
  "pinduoduo": {
    "name": "拼多多",
    "status": "active",
    "profile_id": "pdd_edge",
    "profile_dir": "data/browser_profiles/pdd_edge",
    "pages": {
      "chat": {
        "url": "https://mms.pinduoduo.com/chat-merchant/index.html",
        "selector_profile": "pinduoduo_web"
      },
      "products": {
        "url": "https://mms.pinduoduo.com/goods/index.html",
        "scraper": "PddProductScraper"
      }
    }
  },
  "xianyu": {
    "name": "闲鱼",
    "status": "coming_soon",
    "profile_id": "xianyu_edge",
    "profile_dir": "data/browser_profiles/xianyu_edge",
    "pages": {}
  }
}
```

要求：

- 平台 URL 不要散落在组件或 scraper 中。
- 平台页面、selector profile、scraper 都通过注册表查。
- 非拼多多平台即使展示在 UI，也不能调用拼多多 scraper。

## 8. Local Agent 改造要求

### 8.1 浏览器会话管理

当前 Local Agent 偏命令行启动。

需要新增一个会话管理层：

`app/local_agent/browser_session_manager.py`

职责：

- 按 `platform + page_type + profile_id` 管理浏览器上下文。
- 打开页面。
- 复用已有登录态。
- 查询当前 URL 和标题。
- 检测页面是否登录。
- 关闭页面或停止监听。

### 8.2 Agent 运行管理

新增：

`app/local_agent/agent_process_manager.py`

职责：

- 从 API 启动 watch loop。
- 管理不同平台的运行实例。
- 防止同一个平台同一个 profile 重复启动多个监听进程。
- 支持停止。
- 更新 heartbeat。

### 8.3 运行模式

统一三种模式：

| 模式 | 行为 | 适用场景 |
| --- | --- | --- |
| `dry_run` | 只读取消息、生成回复、记录决策，不回填不发送 | 调试、验收、安全测试 |
| `assist` | 生成回复并回填输入框，不点击发送 | 半托管，人工确认 |
| `auto` | 低风险自动发送，高风险转人工 | 全托管 |

底层仍保留 `--allow-real-send` 保险。

即使 UI 选择 `auto`，如果底层没有开启真实发送权限，也必须降级为 dry-run 或 assist，并在 UI 明确显示。

## 9. 商品抓取流程详细实现

### 9.1 前端流程

修改 `ProductManagement.tsx`：

1. 点击“从平台抓取”。
2. 打开 `ProductScrapeWizard` 弹窗。
3. 弹窗加载当前平台抓取能力：
   - `GET /api/platform/list`
   - 或新增 `GET /api/platform-browser/capabilities`
4. 用户点击“打开平台商品页”。
5. 调用：
   - `POST /api/platform-browser/open`
   - `page_type=products`
6. 用户在浏览器中登录。
7. 用户回到系统点击“检测登录状态”。
8. 调用：
   - `POST /api/platform-browser/check-login`
9. 状态为 `ready` 后，允许点击“开始抓取”。
10. 调用：
    - `POST /api/products/scrape`
11. 轮询任务状态。
12. 抓取完成后刷新商品列表。

### 9.2 后端流程

`POST /api/products/scrape` 需要支持：

```json
{
  "merchant_id": "default",
  "platform": "pinduoduo",
  "profile_id": "pdd_edge",
  "user_data_dir": "data/browser_profiles/pdd_edge",
  "mode": "all",
  "max_pages": 3
}
```

其中：

- `profile_id` 用于查 profile 路径。
- `user_data_dir` 可选，前端一般不直接传绝对路径。
- `mode` 可选：
  - `all`
  - `current_page`
  - `selected`
- 第一阶段只实现 `all`。

### 9.3 登录状态检测规则

拼多多商品页检测规则：

满足任一条件认为未登录：

- URL 包含 `/login`。
- 页面存在扫码登录框。
- 页面标题包含登录。
- 找不到商品管理页面核心元素。

满足以下条件认为 ready：

- URL 在 `mms.pinduoduo.com`。
- 页面不是登录页。
- 检测到商品列表容器、商品管理菜单、或商品搜索框。

检测逻辑应放在拼多多 adapter/profile 内，不要写死在通用代码里。

## 10. 客服工作台流程详细实现

### 10.1 前端新增组件

新增：

- `frontend/src/components/PlatformBrowserWorkbench.tsx`
- `frontend/src/components/PlatformAccountList.tsx`
- `frontend/src/components/PlatformSessionPanel.tsx`
- `frontend/src/components/AgentDecisionPanel.tsx`

第一版也可以只做一个大组件，后续再拆。

### 10.2 导航改造

修改：

- `Sidebar.tsx`
- `App.tsx`

新增导航项：

- `客服工作台`

`NavView` 增加：

- `platform-workbench`

`App.tsx` 中：

```tsx
case 'platform-workbench':
  return <PlatformBrowserWorkbench />
```

### 10.3 工作台数据加载

页面加载时：

1. 请求 `/api/platform/list` 获取平台列表。
2. 请求 `/api/platform-browser/sessions` 获取浏览器会话。
3. 每 3-5 秒轮询一次。
4. 合并平台列表和 session 状态。

### 10.4 打开客服页

用户点击拼多多账号的“打开客服页”：

```http
POST /api/platform-browser/open
```

请求：

```json
{
  "platform": "pinduoduo",
  "page_type": "chat",
  "merchant_id": "default",
  "shop_id": "default",
  "profile_id": "pdd_edge",
  "headed": true
}
```

打开后 UI 显示：

- 当前窗口已打开。
- 等待登录或已登录。
- 当前 URL。
- 页面标题。

### 10.5 启动 AI 接待

用户点击“启动 AI 接待”：

```http
POST /api/platform-browser/start-agent
```

请求：

```json
{
  "platform": "pinduoduo",
  "page_type": "chat",
  "merchant_id": "default",
  "shop_id": "default",
  "profile_id": "pdd_edge",
  "mode": "dry_run",
  "interval_seconds": 10
}
```

返回成功后，左侧账号状态变为：

- `监听中`

右侧显示：

- 最新买家消息。
- 当前商品上下文。
- AI 推荐回复。
- 风险等级。
- 自动发送结果。

### 10.6 手动回复

第一阶段手动回复不通过系统前端输入框完成。

用户直接在 Local Agent 打开的真实平台浏览器窗口中手动输入和发送。

前端只负责：

- 显示当前正在监听哪个窗口。
- 显示 AI 推荐回复。
- 显示是否已经自动发送。
- 显示哪些问题转人工。

后续可再增加“复制推荐回复”按钮。

## 11. 数据结构与状态字段

### 11.1 PlatformSession

```ts
interface PlatformSession {
  agent_id: string
  platform: string
  page_type: 'chat' | 'products' | 'orders'
  merchant_id: string
  shop_id?: string
  profile_id: string
  status: 'not_opened' | 'opening' | 'login_required' | 'ready' | 'running' | 'paused' | 'error'
  logged_in: boolean
  current_url?: string
  page_title?: string
  last_heartbeat_at?: string
  error_message?: string
  latest_buyer_message?: string
  latest_decision?: AgentDecision
}
```

### 11.2 AgentDecision

```ts
interface AgentDecision {
  recommended_reply: string
  auto_send_allowed: boolean
  risk_level: 'low' | 'medium' | 'high'
  auto_send_blockers: string[]
  send_status?: 'not_sent' | 'skipped_dry_run' | 'filled_only' | 'success' | 'failed' | 'handoff'
  handoff_required: boolean
  handoff_reason?: string
  product_id?: string
  product_name?: string
  sku?: string
}
```

注意：

- 不要同时使用 `risk_reasons` 和 `auto_send_blockers` 两套字段。
- 后端和前端统一使用 `auto_send_blockers`。
- 商品上下文也要进入 heartbeat，不能只停留在后端 workflow debug 中。

## 12. 多平台扩展规则

第一阶段只支持拼多多，但架构必须按多平台写。

### 12.1 禁止事项

不要在以下位置硬编码拼多多：

- React 组件业务逻辑。
- `routes_products.py` 通用接口。
- `routes_platform_browser.py` 通用接口。
- Agent manager。
- 商品库和知识库逻辑。

允许在以下位置出现拼多多专属逻辑：

- `pinduoduo_web.local.json`
- `PddProductScraper`
- `PddChatAdapter`
- `platforms.json` 中的拼多多配置。
- 拼多多 login detector。

### 12.2 新平台接入必须补齐

每接入一个新平台，必须新增：

1. 平台注册信息。
2. 页面 URL 配置。
3. 浏览器 profile 配置。
4. 客服页 selector profile。
5. 登录状态检测规则。
6. 商品抓取器或 CSV/手动导入替代方案。
7. 测试用例。

## 13. 安全边界

### 13.1 默认不真实发送

所有平台默认必须是 `dry_run`。

真实发送需要同时满足：

1. UI 模式选择 `auto`。
2. 后端风险策略判定 `auto_send_allowed=true`。
3. Local Agent 启动参数允许真实发送。
4. 当前页面识别到的会话是最新买家消息。
5. 没有命中退款、投诉、差评、线下交易、售后纠纷、平台处罚等风险词。

### 13.2 未登录不允许抓取或监听

如果登录状态为：

- `unknown`
- `login_required`
- `error`

则禁止：

- 商品抓取。
- 客服监听。
- 自动发送。

### 13.3 防止历史消息误回复

Agent 启动后默认只处理：

- 最新一条买家消息。
- 且没有处理过的 message_id。

不要默认批量回复历史消息。

## 14. 验收标准

### 14.1 商品抓取验收

拼多多商品抓取应满足：

1. 商品管理页点击“从平台抓取”后打开抓取向导。
2. 点击“打开平台商品页”后弹出浏览器窗口进入拼多多商品后台。
3. 未登录时用户能在浏览器里完成登录。
4. 登录完成后点击“检测登录状态”显示已登录/ready。
5. 点击“开始抓取”后任务开始。
6. 抓取完成后商品列表刷新。
7. 商品平台字段为 `pinduoduo`。
8. 非拼多多平台不会调用拼多多 scraper。
9. 抓取失败时前端显示明确错误。

### 14.2 客服工作台验收

客服工作台应满足：

1. 左侧显示平台列表。
2. 拼多多显示 active，其他平台显示待接入。
3. 点击拼多多后右侧显示拼多多工作区。
4. 用户可以点击“打开客服页”。
5. 未登录时浏览器进入登录页。
6. 登录后检测状态为 ready。
7. 用户可以启动 dry-run 监听。
8. 买家新消息出现后，前端能显示最新买家消息。
9. AI 决策能显示推荐回复、风险等级、是否允许自动发送。
10. 用户仍能在真实平台浏览器窗口手动回复。
11. 停止监听后 Agent 状态变为 paused/stopped。

## 15. 实施步骤

### Step 1：修复前端中文乱码

当前部分前端文件显示乱码，需要先统一保存为 UTF-8。

涉及文件：

- `ProductManagement.tsx`
- `PlatformDetail.tsx`
- `PlatformAccess.tsx`
- `routes_platform.py` 中返回给前端的中文也应确认编码。

验收：

- 浏览器中中文正常。
- `npm run build` 通过。

### Step 2：新增平台页面配置

新增平台配置文件，集中管理：

- 平台名称。
- 平台颜色。
- 商品页 URL。
- 客服页 URL。
- profile 路径。
- selector profile。
- scraper 名称。

验收：

- 拼多多 URL 不再散落在多个组件里。
- 非拼多多平台返回 unsupported。

### Step 3：实现平台浏览器会话管理器

新增：

- `browser_session_manager.py`

实现：

- open page。
- check login。
- get status。
- close session。

验收：

- 能打开拼多多商品页。
- 能打开拼多多客服页。
- 能返回当前 URL 和标题。

### Step 4：实现平台浏览器 API

新增：

- `routes_platform_browser.py`

实现接口：

- `POST /api/platform-browser/open`
- `POST /api/platform-browser/check-login`
- `POST /api/platform-browser/start-agent`
- `POST /api/platform-browser/stop-agent`
- `GET /api/platform-browser/sessions`

验收：

- Swagger 能看到接口。
- curl 能打开页面并返回 session 状态。

### Step 5：改造商品抓取按钮为抓取向导

新增：

- `ProductScrapeWizard.tsx`

改造：

- `ProductManagement.tsx`

验收：

- 点击按钮不再直接抓取。
- 先打开平台页、检测登录、再抓取。

### Step 6：新增客服工作台页面

新增：

- `PlatformBrowserWorkbench.tsx`

修改：

- `Sidebar.tsx`
- `App.tsx`

验收：

- 左侧平台列表。
- 右侧拼多多工作区。
- 可打开客服页。
- 可启动 dry-run。

### Step 7：修复 heartbeat 字段契约

后端 Local Agent heartbeat 统一输出：

- `auto_send_blockers`
- `product_id`
- `product_name`
- `sku`
- `send_status`
- `recommended_reply`

前端统一读取这些字段。

验收：

- 风险原因能正常显示。
- 商品上下文能正常显示。
- dry-run 结果能正常显示。

### Step 8：拼多多真实页面 dry-run 验证

验证流程：

1. 启动后端。
2. 启动前端。
3. 打开客服工作台。
4. 点击拼多多。
5. 打开客服页。
6. 登录。
7. 启动 dry-run。
8. 让买家发一条低风险消息。
9. 前端显示 AI 推荐回复。
10. 不真实发送。

验收：

- 前端状态和真实浏览器页面一致。
- 不会回复历史消息。
- 不会在 dry-run 下真实发送。

### Step 9：真实发送小流量验证

仅在 Step 8 稳定后执行。

条件：

- 选择器稳定。
- 风险策略通过。
- UI 明确显示当前为自动模式。
- 命令行或后端配置允许真实发送。

验收：

- 只对一条低风险消息自动发送。
- 发送后平台页面能看到消息。
- 后端 send result 记录为 success。
- 前端最近发送记录显示 success。

## 16. 测试计划

### 16.1 后端单元测试

新增测试：

- 平台配置加载测试。
- 不支持平台拒绝测试。
- open page 参数校验测试。
- check login 状态解析测试。
- start-agent 防重复启动测试。
- stop-agent 状态更新测试。

### 16.2 前端构建测试

运行：

```powershell
cd D:\develop_python\system\ecommerce-agent-framework\frontend
npm run build
```

### 16.3 手工测试

手工测试必须记录：

- 打开的页面 URL。
- 登录状态。
- 商品抓取数量。
- 最新买家消息。
- AI 推荐回复。
- 是否 dry-run。
- 是否真实发送。

## 17. 当前优先级

建议接下来按以下顺序做：

1. 修复前端乱码。
2. 新增平台浏览器配置和 API。
3. 商品抓取向导。
4. 客服工作台页面。
5. heartbeat 字段对齐。
6. 拼多多 dry-run 验证。
7. 再考虑真实发送。

不要先做更多平台。先把拼多多一条完整链路做扎实。

