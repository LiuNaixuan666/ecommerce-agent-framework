# 拼多多登录保持与客服工作台执行计划

## 1. 本文档目标

本文档用于继续实现“拼多多优先”的本地多平台 AI 客服工作台，解决当前三个阻塞点：

1. 前端点击“打开客服页”“打开商品页”时报错，且未登录时没有可靠跳转到拼多多登录页。
2. 登录态没有明确的持久化策略，用户担心频繁登录、频繁验证。
3. 客服工作台还没有达到预期形态：左侧选择平台，右侧显示对应平台客服页面，并支持消息红点提醒和提示音开关。

本阶段只把拼多多做实。闲鱼、千牛、京东、抖店只保留扩展位，不实现真实抓取和回复。

## 2. 当前已知基础

当前项目已有以下相关模块：

- 前端工作台组件：`frontend/src/components/PlatformBrowserWorkbench.tsx`
- 商品抓取引导组件：`frontend/src/components/ProductScrapeWizard.tsx`
- 平台浏览器 API：`app/api/routes_platform_browser.py`
- 浏览器会话管理器：`app/local_agent/browser_session_manager.py`
- 平台注册表：`app/local_agent/platforms/__init__.py`
- 拼多多客服选择器配置：`app/local_agent/browser_profiles/pinduoduo_web.local.json`
- 拼多多模板配置：`app/local_agent/browser_profiles/pinduoduo_web.template.json`

但是当前实现还只是“外部浏览器控制雏形”，不是完整产品闭环。

## 3. 拼多多固定入口

本阶段拼多多页面统一使用以下 URL：

```text
登录页：https://mms.pinduoduo.com/login/
首页：https://mms.pinduoduo.com/home/
商品列表：https://mms.pinduoduo.com/goods/index.html
网页版客服：https://mms.pinduoduo.com/chat-merchant/index.html?r=0.5059661250802192#/
```

后续所有代码里不要散落硬编码 URL。应统一放在平台注册表或平台配置文件里。

## 4. 当前问题判断

### 4.1 打开页面报错

重点检查：

- 前端请求 `/api/platform-browser/open` 时是否拿到了非 200 响应。
- 后端是否因为 `platform` 不是 active 而拒绝。
- 后端是否因为 `page_type` 未配置 URL 而拒绝。
- Playwright 是否未安装或浏览器启动失败。
- `data/browser_profiles/pdd_edge` 是否被另一个 Chromium/Edge 实例占用。
- 当前 session key 设计为 `{platform}:{page_type}:{profile_id}`，如果 chat 和 products 同时打开，可能用同一个 profile 创建多个 persistent context，导致浏览器 profile 锁冲突。

需要先让前端显示后端返回的真实错误，而不是按钮点了以后无反馈。

### 4.2 未登录时没有跳登录页

当前后端大概率直接打开目标页，例如商品页或客服页，然后依赖拼多多自己重定向登录页。这个行为不稳定。

正确策略：

- 如果打开目标页后检测到未登录，主动导航到 `https://mms.pinduoduo.com/login/`。
- 用户完成登录后，再由系统跳转回原目标页。
- 登录检测失败时，前端必须显示“请在弹出的浏览器中完成拼多多登录，然后点击检测登录状态”。

### 4.3 登录态保持不明确

当前使用持久化浏览器 profile 是正确方向，但需要明确规则：

- 拼多多使用固定 profile：`data/browser_profiles/pdd_edge`
- 登录信息保存在该 profile 的 Cookie、localStorage、IndexedDB 等浏览器数据中。
- 不要每次打开页面都创建新的临时 profile。
- 不要清理 `data/browser_profiles/pdd_edge`。
- 不要同时用多个 persistent context 打开同一个 profile。

只要拼多多自身 session 没过期，用户登录一次后，后续打开客服页、商品页应复用同一个 profile，不需要频繁扫码。

### 4.4 工作台右侧显示真实平台页的技术边界

普通 React 网页不能可靠地把拼多多后台嵌入 iframe，原因：

- 拼多多可能设置 `X-Frame-Options` 或 CSP，禁止第三方 iframe 嵌入。
- 即使能嵌入，React 前端也不能跨域读取拼多多 DOM。
- 自动回复需要读消息、填输入框、点发送，这些必须由 Playwright、Electron WebView 或浏览器自动化控制层完成。

因此实现分两步：

1. 第一阶段：Web 前端工作台 + 外部 Playwright/Edge 窗口。先把登录、抓取、监听、回复跑通。
2. 第二阶段：Electron/WebView2 桌面壳。左侧 React 控制台，右侧真正显示拼多多页面。

如果用户明确要求“右侧就是拼多多页面”，最终应做 Electron/WebView2，而不是强行 iframe。

## 5. 目标产品形态

### 5.1 第一阶段：可用版 Web 工作台

页面形态：

```text
┌─────────────────────────────────────────────────────────────┐
│ 本地 AI 客服工作台       当前模式：dry-run / assist / auto   │
├───────────────┬─────────────────────────────────────────────┤
│ 左侧平台列表   │ 右侧控制台                                   │
│               │                                             │
│ 拼多多  ●红点  │ 平台：拼多多                                  │
│ 已登录/监听中  │ 登录状态：已登录 / 需登录 / 未检测              │
│ 未读 3         │ 当前页面：客服页 / 商品页 / 登录页              │
│ 🔇/🔊          │                                             │
│               │ [打开登录页] [打开客服页] [打开商品页]          │
│ 闲鱼 待接入    │ [检测登录] [启动监听] [暂停监听]                │
│ 千牛 待接入    │                                             │
│               │ 最新买家消息                                  │
│               │ AI 推荐回复                                   │
│               │ 风险等级 / 是否自动发送 / 阻止原因              │
│               │ 最近发送记录 / 转人工队列                       │
└───────────────┴─────────────────────────────────────────────┘
```

真实拼多多页面暂时在外部 Edge/Chromium 窗口打开。前端右侧显示控制状态和 Agent 运行结果。

### 5.2 第二阶段：桌面内嵌版工作台

当第一阶段稳定后，再做桌面壳：

```text
┌─────────────────────────────────────────────────────────────┐
│ 本地 AI 客服工作台 Desktop                                  │
├───────────────┬─────────────────────────────────────────────┤
│ 左侧平台列表   │ 右侧 BrowserView/WebView2                    │
│ 拼多多 ●未读   │ 直接显示拼多多客服页面                         │
│ 闲鱼 待接入    │ 用户可手动操作，Agent 可自动读取/回填/发送        │
└───────────────┴─────────────────────────────────────────────┘
```

桌面壳可选技术：

- Electron + BrowserView
- Tauri + WebView2
- pywebview + Edge WebView2

当前更推荐 Electron，因为前端已有 React/Vite，后续能较自然地复用页面。

## 6. 后端改造计划

### Step 1：统一平台 URL 配置

修改 `app/local_agent/platforms/__init__.py` 或拆出新的配置文件，拼多多配置必须包含：

```python
{
    "code": "pinduoduo",
    "name": "拼多多",
    "status": "active",
    "profile_id": "pdd_edge",
    "profile_dir": "data/browser_profiles/pdd_edge",
    "pages": {
        "login": "https://mms.pinduoduo.com/login/",
        "home": "https://mms.pinduoduo.com/home/",
        "products": "https://mms.pinduoduo.com/goods/index.html",
        "chat": "https://mms.pinduoduo.com/chat-merchant/index.html?r=0.5059661250802192#/"
    }
}
```

验收：

- `/api/platform-browser/open` 支持 `page_type=login|home|products|chat`
- 未配置 page_type 时返回清晰错误。

### Step 2：重构 BrowserSessionManager 的 profile 使用方式

当前风险：同一个 `pdd_edge` profile 可能被 chat/products 两个 persistent context 同时打开。

目标：

- 一个 `platform + profile_id` 只启动一个 persistent browser context。
- chat、products、login 是同一个 context 下的不同 page/tab。
- session 可以按 page_type 查询，但底层 context 不能重复启动。

建议内部模型：

```python
BrowserContextHandle:
    platform
    profile_id
    profile_dir
    playwright
    context
    pages: dict[page_type, page]
    last_used_at

BrowserPageSession:
    session_id
    platform
    page_type
    profile_id
    status
    logged_in
    current_url
    page_title
    error_message
```

验收：

- 连续点击“打开客服页”“打开商品页”不会触发 profile lock。
- 两个页面复用 `data/browser_profiles/pdd_edge` 登录态。
- 关闭会话时不要误删 profile 数据。

### Step 3：实现拼多多登录检测器

不要用乱码关键词或通用字符串硬猜。新增平台专用检测器，例如：

```text
app/local_agent/platforms/pinduoduo_login_detector.py
```

检测逻辑：

未登录条件：

- URL 包含 `/login`
- 页面文本包含：`登录`、`扫码登录`、`手机登录`、`密码登录`
- 出现登录二维码或账号密码输入区域

客服页 ready 条件：

- URL 包含 `chat-merchant`
- 页面出现客服会话列表、消息区域、输入框或发送按钮
- 至少命中一个已配置的客服选择器，例如 `#replyTextarea` 或 `div.send-btn`

商品页 ready 条件：

- URL 包含 `/goods/`
- 页面出现商品列表、商品搜索框、商品管理、发布商品等关键词或对应 DOM

首页 ready 条件：

- URL 包含 `/home`
- 页面出现店铺后台、数据概览、商家后台等关键词或主布局 DOM

返回结构：

```json
{
  "logged_in": true,
  "status": "ready",
  "page_kind": "chat",
  "reason": "detected_chat_dom",
  "current_url": "...",
  "page_title": "..."
}
```

验收：

- 未登录时明确返回 `login_required`
- 已登录客服页返回 `ready`
- 已登录商品页返回 `ready`
- 检测失败时返回 `unknown` 或 `error`，不要误判为 ready。

### Step 4：打开目标页时增加登录兜底

`open_session/open_page` 流程改为：

1. 打开目标 URL。
2. 执行登录检测。
3. 如果检测为未登录：
   - 导航到登录 URL。
   - session.status = `login_required`
   - session.target_after_login = 原目标 page_type。
4. 用户登录后点击“检测登录”。
5. 检测到已登录后自动跳转到原目标页。

验收：

- 未登录点击“打开客服页”，浏览器最终停在拼多多登录页。
- 登录完成后点击“检测登录”，自动进入客服页。
- 未登录点击“打开商品页”，同样先登录，登录后自动进入商品页。

### Step 5：新增浏览器会话 API

现有接口保留，但建议补齐：

```http
POST /api/platform-browser/open
POST /api/platform-browser/check-login
POST /api/platform-browser/focus
POST /api/platform-browser/refresh
POST /api/platform-browser/close
GET  /api/platform-browser/sessions
```

`open` 请求：

```json
{
  "platform": "pinduoduo",
  "page_type": "chat",
  "profile_id": "pdd_edge",
  "headed": true
}
```

`open` 返回：

```json
{
  "ok": true,
  "session": {
    "platform": "pinduoduo",
    "page_type": "chat",
    "status": "login_required",
    "logged_in": false,
    "current_url": "https://mms.pinduoduo.com/login/",
    "target_after_login": "chat"
  }
}
```

所有接口失败时统一返回：

```json
{
  "ok": false,
  "error_code": "PLAYWRIGHT_PROFILE_LOCKED",
  "message": "拼多多浏览器 profile 正在被另一个窗口占用，请关闭旧窗口后重试。"
}
```

验收：

- 前端能展示具体错误。
- 不再出现按钮点击后无反馈。

### Step 6：让 start-agent 真正启动监听

当前 `/api/platform-browser/start-agent` 不能只改 session.status。它必须启动或调度真实 Local Agent 循环。

最低可用方案：

- 后端创建后台 task/thread。
- 复用已打开的 chat page。
- 调用现有 BrowserPageWatcher、BrowserPageContextExtractor、BrowserPageReplyExecutor。
- 调用 `/api/chat/rpa/message` 获取决策。
- dry-run 模式不回填、不点击发送。
- assist 模式只回填输入框，不点击发送。
- auto 模式需要 `auto_send_allowed=true` 才点击发送。

验收：

- 启动监听后 `/api/local-agent/status` 能看到 running agent。
- 页面有新买家消息时，heartbeat 记录 `latest_buyer_message`。
- dry-run 能生成回复但不发送。
- auto 模式必须经过风险闸门。

## 7. 前端改造计划

### Step 1：修复按钮错误反馈

所有 `fetch` 必须检查 `res.ok`。

错误时显示：

- 错误标题
- 后端 message
- 建议操作

例如：

```text
打开拼多多客服页失败
原因：Playwright 未安装
建议：执行 pip install playwright，然后重启后端
```

验收：

- 后端 4xx/5xx 时前端不再静默失败。
- 用户知道下一步该做什么。

### Step 2：修复 page_type 错误

`PlatformBrowserWorkbench.tsx` 当前检查登录时固定传 `page_type: "chat"`，需要改成当前页面类型。

状态中增加：

```ts
const [activePageType, setActivePageType] = useState<'login' | 'home' | 'chat' | 'products'>('chat')
```

点击“打开客服页”：

```ts
setActivePageType('chat')
openPage('chat')
```

点击“打开商品页”：

```ts
setActivePageType('products')
openPage('products')
```

检测登录：

```ts
checkLogin(activePageType)
```

验收：

- 打开商品页后检测的是 products session，不是 chat session。
- 打开客服页后检测的是 chat session。

### Step 3：增加“打开登录页”

右侧操作区新增按钮：

- 打开登录页
- 打开客服页
- 打开商品页
- 检测登录
- 刷新当前页
- 聚焦浏览器窗口

未登录状态下，主按钮提示：

```text
请先打开登录页并完成拼多多登录
```

验收：

- 用户可以主动打开登录页。
- 未登录时不会误以为已经进入商品/客服页。

### Step 4：左侧平台列表增加消息提醒

平台卡片字段：

```ts
interface PlatformNotificationState {
  unread_count: number
  has_new_message: boolean
  latest_message_preview?: string
  sound_enabled: boolean
  last_seen_message_id?: string
}
```

左侧显示：

- 平台图标
- 平台名称
- 登录状态
- Agent 状态
- 红点或未读数
- 静音按钮

红点规则：

- `unread_count > 0` 显示红点。
- 当前选中平台且用户点击“标记已读”后清零。
- 手动切换到该平台时可以自动清零，也可以保留，第一版建议切换后清零。

验收：

- 新消息进入后拼多多卡片右上角出现红点。
- 点击拼多多卡片后红点消失或未读数清零。

### Step 5：增加提示音开关

前端增加全局或平台级设置：

```ts
soundEnabledByPlatform: Record<string, boolean>
```

持久化优先用 localStorage：

```text
localStorage["platform_sound_settings"]
```

播放条件：

- 有新的 buyer message。
- 当前平台 sound_enabled = true。
- 新消息 ID 没有播放过。

第一版提示音可以使用浏览器原生 Audio：

```ts
new Audio('/sounds/new-message.mp3').play()
```

如果没有声音文件，可以先用 Web Audio API 生成短提示音。

验收：

- 开启声音时新消息播放一次提示音。
- 关闭声音后新消息只显示红点，不播放声音。

### Step 6：右侧状态区显示真实运行信息

右侧不只显示按钮，还要展示：

- 当前浏览器 URL
- 当前页面标题
- 登录状态
- 当前 page_type
- 最近一次检测时间
- 最新买家消息
- 当前商品上下文
- AI 推荐回复
- 风险等级
- `auto_send_allowed`
- `auto_send_blockers`
- 最近发送结果

验收：

- 用户不用看命令行，也能判断 Agent 是否真的在读页面、生成回复、发送或转人工。

## 8. 商品抓取流程改造

### 8.1 商品页打开流程

点击“从平台抓取”后：

1. 弹出抓取向导。
2. 用户点击“打开拼多多商品页”。
3. 后端打开 products 页。
4. 如果未登录，跳到登录页。
5. 用户登录后点击“检测登录”。
6. 系统进入商品页。
7. 用户确认页面已显示商品列表。
8. 用户点击“开始抓取”。

### 8.2 抓取器复用已打开页面

当前如果抓取器另起一个浏览器，可能再次触发登录或 profile 锁。

目标：

- 商品抓取优先复用 `BrowserSessionManager` 中已打开的 products page。
- 如果没有已打开 products page，再启动同一 profile 的 page。
- 不要另起独立 persistent context。

验收：

- 用户在工作台登录后，商品抓取不再要求重复登录。
- 商品抓取使用同一个 `pdd_edge` profile。

## 9. 登录保持策略

### 9.1 什么情况下保持登录

只要满足：

- `data/browser_profiles/pdd_edge` 未删除
- 拼多多 Cookie 未过期
- 拼多多没有风控要求重新验证
- 没有同时多个 persistent context 争抢该 profile

则应该保持登录。

### 9.2 什么情况下仍然需要重新登录

以下情况无法避免：

- 拼多多主动让 session 过期。
- 用户手动退出登录。
- 拼多多检测到异常，需要重新扫码或验证。
- profile 被删除或换了路径。
- 不同系统用户/不同机器使用同一项目但没有同一浏览器 profile。

前端文案必须明确：

```text
登录状态由拼多多平台控制。系统会保存本地浏览器登录态，但如果拼多多要求重新验证，需要商家再次登录。
```

### 9.3 登录检测频率

不要频繁强校验登录。建议：

- 页面打开后检测一次。
- 用户点击“检测登录”时检测一次。
- 启动监听前检测一次。
- 抓取商品前检测一次。
- 运行中每 3 到 10 分钟轻量检测一次。
- 遇到登录页、验证码页、发送失败时立即检测。

缓存字段：

```text
last_login_checked_at
login_check_ttl_seconds = 300
login_status_source = cached | live
```

验收：

- 前端轮询 session 时不导致页面频繁刷新或重新登录。
- 登录状态缓存不会误导关键操作，启动监听和抓取前仍会 live check。

## 10. 通知数据流

### 10.1 后端状态字段

Local Agent heartbeat 增加或复用：

```json
{
  "agent_id": "pinduoduo-default-chat",
  "platform": "pinduoduo",
  "status": "running",
  "latest_buyer_message": "这个有货吗",
  "latest_message_id": "pdd-message-xxx",
  "latest_message_at": "2026-06-29T10:00:00",
  "unread_count": 1,
  "notification": {
    "has_new_message": true,
    "sound_recommended": true
  }
}
```

### 10.2 前端去重逻辑

前端维护：

```ts
lastPlayedMessageIdByPlatform
lastSeenMessageIdByPlatform
```

当轮询发现 `latest_message_id` 变化：

- 对应平台未读数 +1。
- 如果声音开启，播放提示音。
- 当前平台卡片显示红点。

验收：

- 同一条消息不会重复响铃。
- 页面轮询不会造成持续播放。

## 11. 自动回复模式

工作台必须明确三种模式：

### dry-run

- 读取消息。
- 生成 AI 回复。
- 记录风险判断。
- 不回填输入框。
- 不点击发送。

用于测试。

### assist

- 读取消息。
- 生成 AI 回复。
- 回填到平台输入框。
- 不点击发送。

用于半托管。

### auto

- 读取消息。
- 生成 AI 回复。
- 如果 `auto_send_allowed=true`，自动点击发送。
- 如果风险高或证据不足，转人工。

用于全托管。

验收：

- 默认模式必须是 `dry-run`。
- 切到 `auto` 前需要前端二次确认。
- `auto` 也必须尊重后端风险策略，不能绕过 `auto_send_allowed`。

## 12. 详细实施顺序

### P0：先让页面能打开、能登录、能保持登录

1. 修复平台 URL 配置，加入 login/home/products/chat。
2. 修复 `/api/platform-browser/open`，支持 page_type=login。
3. 修复打开目标页后的登录兜底：未登录主动跳 login。
4. 修复前端 fetch 错误展示。
5. 修复前端 page_type 错误。
6. 修复 profile 复用，避免同一个 pdd_edge 同时开多个 persistent context。
7. 手动验证：
   - 点击打开登录页。
   - 扫码登录。
   - 点击打开客服页。
   - 点击打开商品页。
   - 关闭前端刷新后，再打开客服页，不重复登录。

### P1：让商品抓取能用登录态跑通

1. 商品抓取向导先调用 `open products`。
2. 未登录时引导登录。
3. 已登录后进入商品列表。
4. 抓取器复用已打开 products page。
5. 抓取成功后写入商品库。
6. 前端商品列表按平台刷新。

### P2：让客服监听和回复真正跑通

1. `start-agent` 启动真实 Local Agent loop。
2. dry-run 读取最新买家消息。
3. heartbeat 回传最新消息和推荐回复。
4. assist 回填输入框。
5. auto 在低风险下真实发送。
6. 发送结果写回 `/api/chat/rpa/send-result`。

### P3：消息红点与声音提醒

1. 后端 heartbeat 增加 latest_message_id。
2. 前端识别新消息。
3. 左侧平台卡片显示红点。
4. 新消息播放提示音。
5. 加入静音开关。
6. 静音设置持久化。

### P4：桌面内嵌工作台

如果必须右侧显示真实拼多多页面，进入这一阶段：

1. 新建 Electron 壳。
2. 复用 React 前端作为左侧控制台。
3. 右侧用 BrowserView 加载拼多多客服页。
4. 使用固定 partition/profile 保存登录态。
5. Local Agent 通过 CDP 或 Electron 主进程控制该页面。
6. 保留外部浏览器模式作为 fallback。

## 13. 验收清单

### 登录与页面打开

- [ ] 点击“打开登录页”能打开拼多多登录页。
- [ ] 点击“打开客服页”未登录时能跳到登录页。
- [ ] 登录后能进入拼多多客服页。
- [ ] 点击“打开商品页”能进入商品列表。
- [ ] 刷新前端或重启后端后，只要 profile 未失效，不需要重新登录。
- [ ] 后端返回错误时前端能显示具体原因。

### 商品抓取

- [ ] 已登录状态下能从拼多多商品页抓取商品。
- [ ] 抓取结果写入本地商品库。
- [ ] 前端商品管理页只显示当前平台商品。
- [ ] 不会因为 profile 锁导致抓取失败。

### 客服监听

- [ ] 启动 dry-run 后能读取最新买家消息。
- [ ] 能生成 AI 推荐回复。
- [ ] 能在前端显示风险等级和是否允许自动发送。
- [ ] assist 模式只回填不发送。
- [ ] auto 模式只在 `auto_send_allowed=true` 时发送。
- [ ] 高风险、退货投诉、证据不足问题转人工。

### 消息提醒

- [ ] 新买家消息出现后左侧拼多多卡片显示红点。
- [ ] 未读数量正确增加。
- [ ] 点击平台后可清除红点。
- [ ] 声音开启时新消息响一次。
- [ ] 静音后不再播放声音。

### 工作台形态

- [ ] Web 第一阶段能清晰显示平台状态、登录状态、页面 URL、Agent 状态。
- [ ] 如果进入 Electron 阶段，右侧能直接显示拼多多客服页。
- [ ] 用户仍可手动回复消息。

## 14. 推荐测试命令

后端：

```powershell
cd D:\develop_python\system\ecommerce-agent-framework
D:\anaconda3\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd D:\develop_python\system\ecommerce-agent-framework\frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

检查后端健康：

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/platform-browser/sessions
```

手动打开拼多多登录页：

```powershell
curl -X POST http://127.0.0.1:8000/api/platform-browser/open `
  -H "Content-Type: application/json" `
  -d "{\"platform\":\"pinduoduo\",\"page_type\":\"login\",\"profile_id\":\"pdd_edge\",\"headed\":true}"
```

手动打开拼多多客服页：

```powershell
curl -X POST http://127.0.0.1:8000/api/platform-browser/open `
  -H "Content-Type: application/json" `
  -d "{\"platform\":\"pinduoduo\",\"page_type\":\"chat\",\"profile_id\":\"pdd_edge\",\"headed\":true}"
```

手动打开拼多多商品页：

```powershell
curl -X POST http://127.0.0.1:8000/api/platform-browser/open `
  -H "Content-Type: application/json" `
  -d "{\"platform\":\"pinduoduo\",\"page_type\":\"products\",\"profile_id\":\"pdd_edge\",\"headed\":true}"
```

检测登录：

```powershell
curl -X POST http://127.0.0.1:8000/api/platform-browser/check-login `
  -H "Content-Type: application/json" `
  -d "{\"platform\":\"pinduoduo\",\"page_type\":\"chat\",\"profile_id\":\"pdd_edge\"}"
```

## 15. 风险与注意事项

1. 拼多多可能更新 DOM，选择器需要可配置。
2. 拼多多可能要求重新扫码，这是平台行为，系统只能复用登录态，不能永久绕过验证。
3. 同一个 profile 不能被多个 persistent context 同时占用。
4. 普通 Web 前端不能可靠内嵌拼多多后台，真正内嵌需要桌面壳。
5. 真实自动发送必须默认关闭，先 dry-run，再 assist，最后小范围 auto。
6. 所有自动发送都必须经过 `auto_send_allowed` 和风险策略。

## 16. 下一步建议

下一轮直接从 P0 开始，不先做 Electron：

1. 修复 `/api/platform-browser/open` 支持 login URL 和登录兜底。
2. 修复 BrowserSessionManager 的 profile 复用。
3. 修复前端错误展示和 page_type 传参。
4. 手动跑通拼多多登录保持。

只有当“外部浏览器模式”已经能稳定登录、抓商品、读消息、dry-run 回复后，再投入 Electron 内嵌工作台。
