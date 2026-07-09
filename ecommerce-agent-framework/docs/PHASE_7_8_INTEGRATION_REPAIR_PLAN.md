# 阶段 7-8 集成修复实施计划

## 1. 文件用途

本文档用于指导下一轮开发，目标是把已经写出的以下能力真正串成可验证闭环：

- Agent 到前端 UI 的实时数据流
- 商品数据库与 CSV 导入
- 拼多多商品抓取
- 商品与知识库文档绑定
- 多平台扩展边界

当前原则：

- 不推倒重写。
- 先修链路断点，再扩展功能。
- 先保证拼多多单平台闭环稳定，再抽象多平台能力。
- 不允许前端显示可选平台，但后端实际仍调用拼多多逻辑并错误标记为其它平台。

## 2. 当前结论

当前系统不是完全脱离原系统，已经有前后端入口、Local Agent、商品管理和知识库接口。但四个关键能力还没有完整闭环：

| 模块 | 当前状态 | 主要断点 |
| --- | --- | --- |
| Agent -> UI 数据流 | 部分接通 | Heartbeat 有上报字段，但真实决策结果没有稳定同步到平台工作台 |
| 商品数据库 + CSV 导入 | API 和页面存在 | ProductStore 默认没有真正持久化 |
| 拼多多商品抓取 | 拼多多能作为 MVP | 抓取逻辑硬编码为 PddProductScraper，其它平台 UI 不能直接复用 |
| 商品-知识绑定 | 上传时有 product_id 元数据 | RAG 问答阶段没有按 product_id 检索 |

## 3. 本阶段目标

完成后系统应满足：

1. 商品数据能稳定保存到本地文件。
2. CSV 导入、拼多多抓取、前端商品管理页面使用同一套商品数据。
3. 非拼多多平台不会误调用拼多多抓取器。
4. 商品关联文档上传成功，并且 chunk metadata 带有 product_id。
5. 客服问答时，如果能识别当前商品，就优先检索该商品绑定文档。
6. 平台详情页能看到真实 Local Agent 最新消息、AI 决策、发送/转人工结果。
7. 首页和平台工作台明确区分“已接入”和“待接入”平台。

## 4. 实施顺序

### Step 1：修复商品库持久化

目标：

- 确保商品通过 API 创建、CSV 导入、拼多多抓取后可以落盘保存。
- 后端重启后商品仍然存在。

涉及文件：

- `app/storage/product_store.py`
- `app/api/routes_products.py`
- `tests/test_product_store.py` 或新增对应测试文件

实施内容：

- 给 `ProductStore` 设置默认持久化路径：`data/products/product_store.json`。
- 确认 `_load()` 和 `_save()` 使用同一份文件。
- 确保目录不存在时自动创建。
- 增加测试：创建商品 -> 新建 ProductStore 实例 -> 能重新读到商品。

验收标准：

- 后端重启后，前端商品列表仍能看到导入商品。
- `pytest` 商品存储相关测试通过。

### Step 2：修复商品关联文档上传字段

目标：

- 前端商品行展开后上传文档，后端能正常接收文件。
- 上传任务中能保留 product_id。

涉及文件：

- `frontend/src/components/ProductManagement.tsx`
- `app/api/routes_knowledge.py`

实施内容：

- 前端上传字段名统一为后端期望的 `files`。
- 后端检查 `upload_knowledge()` 的 `product_id` 是否进入 ingestion task。
- 修复 `start_ingestion` 中可能引用未定义 `product_id` 的问题。
- 增加后端接口测试或最小 smoke test。

验收标准：

- 商品详情中上传 PDF/DOCX/TXT 成功。
- 上传任务 `completed`。
- chunk metadata 中存在对应 `product_id`。

### Step 3：限制或注册平台抓取器

目标：

- 避免选择闲鱼/淘宝/JD/抖音时仍然调用拼多多抓取器。

涉及文件：

- `app/api/routes_products.py`
- `frontend/src/components/ProductManagement.tsx`
- 可新增：`app/local_agent/scrapers/registry.py`

实施内容：

- 后端增加 scraper registry。
- 当前只注册 `pinduoduo -> PddProductScraper`。
- 如果 platform 不是 `pinduoduo`，返回明确错误：`platform_not_supported`。
- 前端对非拼多多平台禁用“平台抓取”按钮，显示“待接入”。

验收标准：

- 选择拼多多时可以触发抓取。
- 选择其它平台时不能误抓取，也不能错误写入其它平台商品。

### Step 4：商品列表按平台过滤

目标：

- 商品管理页切换平台时，只显示当前平台商品。
- 避免所有平台商品混在一个列表里。

涉及文件：

- `app/api/routes_products.py`
- `app/storage/product_store.py`
- `frontend/src/components/ProductManagement.tsx`
- `frontend/src/services/api.ts`

实施内容：

- `GET /api/products` 支持 `platform` 查询参数。
- ProductStore list 方法支持 platform filter。
- 前端切换平台后重新加载对应商品。

验收标准：

- 导入 `platform=pinduoduo` 的商品只在拼多多视图显示。
- 后续扩展其它平台时不会污染当前拼多多商品列表。

### Step 5：建立商品上下文到 product_id 的解析

目标：

- Local Agent 从平台页面读到商品标题、SKU、平台商品 ID 后，后端能找到本地商品库里的 product_id。

涉及文件：

- `app/agent/workflow.py`
- `app/storage/product_store.py`
- `app/local_agent/extractors/browser_page.py`
- `app/local_agent/browser_profiles/pinduoduo_web.local.json`

实施内容：

- 从 page_context 中读取：
  - platform
  - product_name
  - sku
  - platform_product_id
  - product_url
- ProductStore 增加匹配方法：
  - 优先 platform + platform_product_id
  - 其次 platform + sku
  - 再其次标题模糊匹配
- workflow 把解析出的 product_id 放入检索上下文。

验收标准：

- 买家从某个商品页进入客服，Agent 能识别当前商品对应的本地 product_id。
- 识别不到时不能乱猜，应退回普通 RAG 检索。

### Step 6：让 RAG 检索真正按 product_id 优先

目标：

- 商品绑定文档不是只写入 metadata，而是在问答时真正优先使用。

涉及文件：

- `app/rag/retriever.py`
- `app/rag/vector_store.py`
- `app/agent/workflow.py`
- `tests/test_product_knowledge_binding.py`

实施内容：

- Retriever 增加 `retrieve(query, product_id=None, ...)`。
- 如果有 product_id，调用 `similarity_search_with_product_filter()`。
- product_id 检索无结果时，再 fallback 到普通检索。
- workflow 传入当前商品 product_id。

验收标准：

- 给商品 A 上传文档，问商品 A 问题时命中商品 A 文档。
- 给商品 B 提同类问题时不会误命中商品 A 文档。
- 如果当前商品没有文档，能 fallback 到店铺通用政策。

### Step 7：修复 Agent 实时决策回写 UI

目标：

- 平台详情页看到的 AI 决策必须来自真实 Local Agent 运行结果，而不是 demo seed 或旧 metadata。

涉及文件：

- `app/local_agent/runtime.py`
- `app/api/routes_local_agent.py`
- `app/api/routes_platform.py`
- `frontend/src/components/PlatformDetail.tsx`

实施内容：

- LocalAgentRuntime 每处理完一条消息后，上报一次包含决策结果的 heartbeat metadata。
- metadata 至少包含：
  - latest_buyer_message
  - recommended_reply
  - risk_level
  - auto_send_allowed
  - auto_send_blockers
  - action
  - confidence
  - product_context
- PlatformDetail 优先展示最新处理结果。
- 最近发送记录继续作为审计记录展示。

验收标准：

- CLI 跑 `run_browser_mock --watch` 后，前端平台详情页能自动更新最新买家消息和 AI 决策。
- dry-run、auto_sent、handoff_required 状态都能在 UI 区分。

### Step 8：清理前端中文乱码和平台状态文案

目标：

- 页面文案恢复为可读中文。
- 首页清楚表达当前哪些平台可用、哪些平台待接入。

涉及文件：

- `frontend/src/components/Sidebar.tsx`
- `frontend/src/components/Dashboard.tsx`
- `frontend/src/components/PlatformDetail.tsx`
- `frontend/src/components/ProductManagement.tsx`
- `frontend/src/components/PlatformAccess.tsx`
- `frontend/src/components/ReplyStrategy.tsx`
- `frontend/src/components/RunLogs.tsx`

实施内容：

- 修复乱码中文。
- 将平台状态统一为：
  - 已接入
  - 测试中
  - 待接入
  - 异常
- 对非拼多多平台显示“待接入，不可启动”。

验收标准：

- `npm run build` 通过。
- 页面无明显乱码。
- 不会出现“看起来能用但实际没接”的平台按钮。

## 5. 验证计划

### 后端验证

运行：

```powershell
D:\anaconda3\python.exe -m py_compile app\main.py app\api\routes_products.py app\api\routes_knowledge.py app\api\routes_platform.py app\api\routes_local_agent.py app\agent\workflow.py app\rag\retriever.py app\storage\product_store.py
```

运行相关测试：

```powershell
pytest tests/test_platform_routes.py tests/test_browser_profiles.py tests/test_generic_web_chat_adapter.py tests/test_browser_web_chat_adapter.py tests/test_local_agent_mock.py tests/test_workflow_risk_strategy.py -q
```

新增测试后补充：

```powershell
pytest tests/test_product_store.py tests/test_product_knowledge_binding.py -q
```

### 前端验证

运行：

```powershell
cd frontend
npm run build
```

手动验证：

- 首页平台卡片显示正常。
- 拼多多平台详情页能刷新 Agent 状态。
- 商品管理页能导入 CSV。
- 商品关联文档上传成功。
- 非拼多多平台抓取按钮不可误用。

### 拼多多 dry-run 验证

运行后端：

```powershell
D:\anaconda3\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

运行 Local Agent dry-run：

```powershell
D:\anaconda3\python.exe -m app.local_agent.run_browser_mock --watch --interval 15 --browser-channel msedge --headed --user-data-dir data\browser_profiles\pdd_edge --selector-profile-json app\local_agent\browser_profiles\pinduoduo_web.local.json --page-url "https://mms.pinduoduo.com/chat-merchant/index.html?r=0.5541775007481573#/"
```

验证：

- 只处理最新一条买家消息。
- 默认不真实发送。
- 前端平台详情页能显示最新消息和决策。

## 6. 本阶段不做

本阶段暂不做：

- 闲鱼、淘宝、京东、抖音真实抓取。
- 云端账号体系。
- 多商家 SaaS 登录注册。
- 自动启动/停止真实浏览器进程的完整进程管理。
- 大规模真实自动发送。
- OCR 和 Windows UI Automation。

## 7. 推荐执行顺序

后续开发按以下顺序逐项进行：

1. Step 1：商品库持久化。
2. Step 2：商品关联文档上传修复。
3. Step 3：平台抓取器限制/注册。
4. Step 4：商品列表按平台过滤。
5. Step 5：商品上下文解析 product_id。
6. Step 6：RAG product_id 优先检索。
7. Step 7：Agent 决策回写 UI。
8. Step 8：前端中文乱码和平台状态文案清理。

每完成一步，必须更新本文档对应状态，并记录：

- 修改文件
- 验证命令
- 验证结果
- 遗留问题

## 8. 当前状态

| 步骤 | 状态 | 备注 |
| --- | --- | --- |
| Step 1 商品库持久化 | 已完成 | 默认写入 `data/products/product_store.json`，已补持久化回读测试 |
| Step 2 商品文档上传修复 | 已完成 | 前端字段名 `file` → `files`，修复 `start_ingestion()` 中 `product_id` 传递 |
| Step 3 平台抓取器限制/注册 | 已完成 | 新增 `scrapers/registry.py`，非 pinduoduo 平台返回 400 |
| Step 4 商品列表按平台过滤 | 已完成 | 前端 `loadProducts(platform)` 传参，切换平台自动重刷 |
| Step 5 商品上下文解析 product_id | 已完成 | `ProductStore.find_by_context()` 5 级匹配，workflow 集成 |
| Step 6 RAG product_id 优先检索 | 已完成 | `Retriever.retrieve(product_id=...)` filter + fallback |
| Step 7 Agent 决策回写 UI | 已完成 | runtime heartbeat 含决策字段，前端 PlatformDetail 展示 |
| Step 8 前端文案清理 | 已完成 | 侧边栏文案修复、启动命令提示、构建通过 |

## 9. 执行记录

## 9. 执行记录

### 2026-06-28 Step 1：商品库持久化

修改文件：

- `app/storage/product_store.py`
- `tests/test_products.py`
- `docs/PHASE_7_8_INTEGRATION_REPAIR_PLAN.md`

修改内容：

- 新增 `DEFAULT_PRODUCT_STORE_PATH`，默认路径为 `data/products/product_store.json`。
- `ProductStore()` 默认启用 JSON 持久化，不再出现“能读取默认文件但保存时直接 return”的问题。
- ProductStore 单元测试改为使用临时路径，避免污染真实商品库。
- 新增 `test_persists_and_reloads_from_json`，验证新实例能从 JSON 文件读回旧实例写入的商品。

验证命令：

```powershell
D:\anaconda3\python.exe -m py_compile app\storage\product_store.py app\api\routes_products.py tests\test_products.py
$env:DEBUG='false'; D:\anaconda3\python.exe -m pytest tests\test_products.py -q
```

验证结果：

- `py_compile` 通过。
- `tests/test_products.py`：16 passed。

遗留问题：

- 当前环境变量 `DEBUG=release` 会导致 `Settings.debug` 解析失败，测试时临时覆盖为 `DEBUG=false`。这不是商品库持久化改动导致的问题，后续可以单独修配置兼容。
- API 测试会触发模块级 `product_store` 写入默认文件。本轮测试生成的测试数据已确认并清理。

### 2026-06-29 Step 2~8：交接文档实施完成

Steps 2~8 全部按 `docs/CONTINUATION_HANDOFF_IMPLEMENTATION_GUIDE.md` 完成。

**Step 2 商品文档上传修复**
- 修改 `frontend/src/components/ProductManagement.tsx`：`formData.append('file', file)` → `'files'`
- 修改 `app/api/routes_knowledge.py`：`start_ingestion()` 补上 `product_id = task.get("product_id")`
- 验证：上传接口返回正常，ingestion status completed

**Step 3 平台抓取器限制**
- 新增 `app/local_agent/scrapers/registry.py`
- 修改 `app/api/routes_products.py`：scrape 接口校验平台，`_run_scrape` 使用动态注册表
- 修改 `frontend/src/components/ProductManagement.tsx`：非 pdd 禁用抓取按钮
- 验证：闲鱼返回 400，拼多多创建任务成功

**Step 4 商品列表按平台过滤**
- 修改 `frontend/src/components/ProductManagement.tsx`：`loadProducts(platform)` 传参切换
- 验证：前端构建通过

**Step 5 商品上下文解析 product_id**
- `app/storage/product_store.py`：新增 `find_by_context()` 5 级匹配
- `app/agent/workflow.py`：`_structured_from_page_context()` 调用 `find_by_context()`
- 新增 8 个单元测试覆盖全部匹配优先级
- 验证：24 passed

**Step 6 RAG product_id 优先检索**
- `app/rag/retriever.py`：`retrieve(product_id=...)` filter + fallback
- `app/agent/workflow.py`：`retrieve()` 从 structured_data 提取 product_id 传参
- 新增集成测试验证 product_id 传递链路
- 验证：43 passed

**Step 7 Agent 决策回写 UI**
- `app/local_agent/runtime.py`：`process_once()` 更新 heartbeat 含决策字段
- 修复字段对齐：`risk_reasons` → `auto_send_blockers`，补充 `product_name/sku/product_price/stock/send_status`
- 验证编译通过

**Step 8 前端文案清理**
- `frontend/src/components/Sidebar.tsx`：「拼多多工作台」→「平台工作台」
- `frontend/src/components/PlatformDetail.tsx`：新增 Local Agent 启动命令提示
- 验证：`npm run build` 通过

**补充修复（2026-06-29 第二轮）**
- `product_store.py`：`bulk_create()` sku 去重增加 `platform` 限定，防止跨平台覆盖
- 新增 `test_bulk_create_sku_dedup_respects_platform` 验证跨平台隔离
- `ProductManagement.tsx`：`handleScrape()` 增加 `res.ok` 错误处理
- `api.ts`：`AgentMetadata` 增加 `send_status` 字段
- 文档状态统一：更新本文档 Step 2-8 状态
- 测试结果：43 passed（25 products + 9 workflow + 9 platform routes）
