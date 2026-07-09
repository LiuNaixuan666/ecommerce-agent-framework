# 电商本地 AI 客服项目继续实施交接指南

本文档面向“完全不了解本项目历史”的接手开发者。目标是让接手者按步骤继续完善当前系统，而不是重新设计一套新系统。

## 1. 项目目标

本项目是一个本地运行的多平台电商 AI 客服系统。

核心目标：

1. 商家在本地启动系统。
2. 系统接入不同电商平台的网页版客服后台，当前优先支持拼多多。
3. Local Agent 或浏览器自动化工具读取买家消息、当前商品上下文、平台上下文。
4. 后端 AI 客服根据商品库、文档知识库、通用政策、风险策略生成回复。
5. 低风险问题可以自动发送，高风险或无把握问题转人工。
6. 系统支持商品信息导入、商品文档绑定、问答模板沉淀、后续多平台扩展。

当前方向不是申请平台 API，而是先通过本地浏览器页面自动化验证闭环。

## 2. 当前系统架构概览

当前系统主要由四部分组成：

1. FastAPI 后端
   - 路径：`app/`
   - 负责聊天、知识库、商品库、平台状态、Local Agent 通信。

2. React 前端
   - 路径：`frontend/`
   - 负责商品管理、平台入口、聊天测试、Mock 工作台、平台状态展示。

3. Local Agent
   - 路径：`app/local_agent/`
   - 负责连接浏览器页面，读取客服消息，回填回复，执行发送。

4. 知识库与商品库
   - 文档知识库：Chroma 向量库。
   - 商品库：本地 JSON 持久化，后续可替换为 SQLite 或商家数据库连接器。

## 3. 当前关键入口文件

后端入口：

- `app/main.py`

当前已挂载的 API 路由大致包括：

- `app/api/routes_chat.py`
- `app/api/routes_knowledge.py`
- `app/api/routes_extension.py`
- `app/api/routes_local_agent.py`
- `app/api/routes_platform.py`
- `app/api/routes_products.py`

Agent 逻辑：

- `app/agent/workflow.py`
- `app/agent/intent_parser.py`
- `app/agent/response_generator.py`
- `app/agent/risk_policy.py`

RAG 相关：

- `app/rag/retriever.py`
- `app/rag/vector_store.py`
- `app/knowledge/ingestion.py`
- `app/knowledge/chunking.py`

商品库：

- `app/storage/product_store.py`

Local Agent：

- `app/local_agent/adapters/base.py`
- `app/local_agent/adapters/generic_web_chat.py`
- `app/local_agent/executors/browser_page.py`
- `app/local_agent/run_browser_mock.py`
- `app/local_agent/browser_profiles/pinduoduo_web.local.json`
- `app/local_agent/browser_profiles/pinduoduo_web.template.json`

前端：

- `frontend/src/App.tsx`
- `frontend/src/components/ProductManagement.tsx`
- `frontend/src/components/PlatformAccess.tsx`
- `frontend/src/components/PlatformDetail.tsx`
- `frontend/src/components/MockShopWorkbench.tsx`
- `frontend/src/services/api.ts`

项目进度文档：

- `docs/EXECUTION_TRACKER.md`
- `docs/CURRENT_GOAL_AND_PROGRESS.md`
- `docs/SELF_BUILT_LOCAL_AGENT_PLAN.md`
- `docs/PHASE_7_8_INTEGRATION_REPAIR_PLAN.md`

本交接文档应作为接下来实现的主执行依据。

## 4. 当前已经完成的内容

### 4.1 阶段 0：基础清理

已完成目标：

- 清理旧的测试硬编码话术。
- 整理 `workflow.py`、`intent_parser.py`、`local_client.py`、`routes_chat.py` 中明显不合理的旧流程残留。
- 重写或清理 `response_generator.py` 的乱码 prompt、旧 mock 文案、弱证据组织。
- 增加更严格的质量闸门，避免低证据回答直接自动发送。

### 4.2 阶段 1：结构化客服回复和风险策略

已完成目标：

- 后端回复结果中包含结构化字段。
- RPA 标准接口开始向 `auto_send_allowed` 靠拢。
- 自动发送边界已初步建立。
- 默认不真实发送，真实发送必须显式开启。

### 4.3 阶段 2 到阶段 4：Local Agent 骨架和浏览器闭环

已完成目标：

- 已有 `BasePlatformAdapter` 抽象。
- 已有 `GenericWebChatAdapter`。
- 已有 Mock 客服页面和 Mock Adapter。
- 已有浏览器页面执行器。
- 已有拼多多选择器配置文件。
- 已有 `--allow-real-send` 安全开关。
- 已有“只处理最新一条买家消息”的安全策略，防止回复历史消息。

### 4.4 阶段 7/8 修复计划 Step 1：商品库持久化

已经完成：

- `ProductStore()` 默认写入：

```text
data/products/product_store.json
```

- 测试用例不再污染默认商品库路径。
- 新增了商品库持久化重载测试。

已验证：

```powershell
$env:DEBUG='false'
D:\anaconda3\python.exe -m pytest tests\test_products.py -q
```

结果：

```text
16 passed
```

注意：

当前直接运行 pytest 时，如果环境变量 `DEBUG=release`，Pydantic 配置可能会把它当布尔值解析失败。测试前先设置：

```powershell
$env:DEBUG='false'
```

这是已知环境问题，不是商品库逻辑失败。

## 5. 当前已知问题

接手者应先理解这些问题，不要盲目继续堆功能。

### 5.1 商品文档上传字段名不一致

前端 `ProductManagement.tsx` 上传商品关联文档时，目前可能使用：

```ts
formData.append('file', file)
```

但后端 `routes_knowledge.py` 的 `/api/knowledge/upload` 接口要求字段名：

```python
files: List[UploadFile] = File(...)
```

这会导致商品关联文档上传失败或无法进入正确 ingestion 流程。

### 5.2 知识库手动启动任务时 product_id 可能丢失

`app/api/routes_knowledge.py` 中 `start_ingestion()` 需要确认从 task 中读取：

```python
product_id = task.get("product_id")
```

然后传给后台 ingestion。当前代码中曾出现过 `product_id` 未定义或未传递的问题。

### 5.3 商品抓取接口名义上支持多平台，实际只调用拼多多抓取器

`app/api/routes_products.py` 的 `/api/products/scrape` 接口接收 `platform`，但 `_run_scrape` 当前直接使用 `PddProductScraper`。

风险：

- 前端选择闲鱼、淘宝、京东、抖音时，后端仍可能调用拼多多抓取逻辑。
- 数据会被错误写入非拼多多平台。

必须修复为平台注册表：

- 支持的平台才允许执行抓取。
- 不支持的平台返回明确错误。

### 5.4 商品列表前端没有按平台过滤

`ProductManagement.tsx` 有平台选择器，但 `loadProducts()` 当前可能仍请求：

```text
/api/products?merchant_id=default&limit=200
```

缺少：

```text
platform=pinduoduo
```

这会导致不同平台商品混在一个列表中。

### 5.5 RAG 还没有真正按当前商品 product_id 过滤

知识库 chunk 已经可以带 `product_id` 元数据，向量库也已有按 `product_id` 过滤的方法。

但当前 `workflow.py` 检索时仍大概率是：

```python
retriever.retrieve(query, k=settings.similarity_top_k)
```

还没有把当前会话商品上下文解析成 `product_id`，再传给 RAG 检索。

这是接下来最关键的链路修复之一。

### 5.6 前端有乱码和状态表达不清

部分前端页面存在中文乱码或旧文案。修复功能链路后，需要集中清理 UI 文案。

注意：

- 不要一边改链路一边大规模美化 UI。
- 先保证数据链路正确，再清理文案和交互。

## 6. 本地启动方式

### 6.1 启动后端

在 PowerShell 中：

```powershell
cd D:\develop_python\system\ecommerce-agent-framework
$env:DEBUG='false'
D:\anaconda3\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

验证：

```powershell
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/chat/health
curl http://127.0.0.1:8000/api/knowledge/health
```

### 6.2 启动前端

另开一个 PowerShell：

```powershell
cd D:\develop_python\system\ecommerce-agent-framework\frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

浏览器打开：

```text
http://127.0.0.1:5173
```

### 6.3 运行商品测试

```powershell
cd D:\develop_python\system\ecommerce-agent-framework
$env:DEBUG='false'
D:\anaconda3\python.exe -m pytest tests\test_products.py -q
```

### 6.4 运行拼多多浏览器 dry-run

注意：默认不要真实发送。

```powershell
cd D:\develop_python\system\ecommerce-agent-framework
$env:DEBUG='false'
D:\anaconda3\python.exe -m app.local_agent.run_browser_mock --watch --interval 15 --user-data-dir data/browser_profiles/pdd_edge
```

只有在明确要真实发送低风险测试消息时，才允许加：

```powershell
--allow-real-send
```

不要在真实平台上随便使用：

```powershell
--process-all-visible
```

否则可能批量回复历史消息。

## 7. 继续实施总原则

接下来不要重写项目。应在现有系统上做“收敛式修复”。

原则：

1. 先修数据链路，再做 UI 美化。
2. 先支持拼多多闭环，再抽象多平台扩展。
3. 所有真实发送必须默认关闭。
4. 平台适配必须走注册表，不允许硬编码到业务流程。
5. 商品文档必须能绑定 product_id。
6. RAG 必须优先使用当前商品关联知识。
7. 所有自动发送必须经过风险策略。
8. 每完成一个步骤必须更新 `docs/EXECUTION_TRACKER.md` 和相关计划文档。

## 8. 接下来详细实施计划

下面每个步骤都包括目标、涉及文件、实施内容、测试方式、验收标准。

## Step 0：接手前基线检查

### 目标

确认接手者环境能正常跑项目，避免在未知失败状态上继续开发。

### 操作

1. 查看当前 git 状态：

```powershell
cd D:\develop_python\system\ecommerce-agent-framework
git status --short
```

2. 不要执行：

```powershell
git reset --hard
git checkout -- .
```

除非项目所有者明确允许。

3. 编译核心 Python 文件：

```powershell
$env:DEBUG='false'
D:\anaconda3\python.exe -m py_compile app\storage\product_store.py app\api\routes_products.py app\api\routes_knowledge.py app\agent\workflow.py app\rag\retriever.py app\rag\vector_store.py
```

4. 运行商品测试：

```powershell
$env:DEBUG='false'
D:\anaconda3\python.exe -m pytest tests\test_products.py -q
```

5. 前端构建：

```powershell
cd frontend
npm run build
```

### 验收标准

- 后端核心文件 py_compile 通过。
- 商品测试通过。
- 前端 build 通过。
- 如果失败，先记录失败点，不要进入下一步。

## Step 1：修复商品关联文档上传链路

### 目标

让前端商品管理页上传商品说明文档时，后端能够收到 `product_id`，并将文档 chunk 写入带 `product_id` 的知识库。

### 涉及文件

- `frontend/src/components/ProductManagement.tsx`
- `app/api/routes_knowledge.py`
- `app/knowledge/ingestion.py`
- `app/knowledge/chunking.py`
- `app/rag/vector_store.py`
- `tests/`

### 后端现状

`routes_knowledge.py` 的上传接口应该类似：

```python
async def upload_knowledge(
    merchant_id: str = Form(...),
    files: List[UploadFile] = File(...),
    product_id: Optional[str] = Form(None),
)
```

`ingestion.py` 和 `chunking.py` 已有把 `product_id` 写入 metadata 的基础。

### 实施内容

1. 修改 `ProductManagement.tsx` 商品文档上传表单。

把：

```ts
formData.append('file', file)
```

改为：

```ts
formData.append('files', file)
```

同时确保传入：

```ts
formData.append('merchant_id', 'default')
formData.append('product_id', product.id)
```

2. 修复 `routes_knowledge.py` 中手动启动 ingestion 的 product_id 丢失问题。

如果有类似：

```python
await _background_ingest_task(upload_id, merchant_id, stored_files, product_id)
```

但 `product_id` 未定义，应改为：

```python
product_id = task.get("product_id")
await _background_ingest_task(upload_id, merchant_id, stored_files, product_id)
```

3. 确认 `_background_ingest_task()` 把 `product_id` 传给：

```python
ingest_merchant_documents(..., product_id=product_id)
```

4. 确认 `chunking.py` 中生成 chunk metadata 时包含：

```python
metadata["product_id"] = product_id
```

### 测试方式

后端编译：

```powershell
cd D:\develop_python\system\ecommerce-agent-framework
$env:DEBUG='false'
D:\anaconda3\python.exe -m py_compile app\api\routes_knowledge.py app\knowledge\ingestion.py app\knowledge\chunking.py
```

前端构建：

```powershell
cd frontend
npm run build
```

接口测试建议：

```powershell
curl -X POST `
  -F "merchant_id=default" `
  -F "product_id=test-product-001" `
  -F "files=@D:\develop_python\system\ecommerce-agent-framework\data\test_docs\product.txt" `
  http://127.0.0.1:8000/api/knowledge/upload
```

### 验收标准

- 上传请求成功。
- 后端 task 中能看到 `product_id`。
- ingestion 不报错。
- Chroma 中对应 chunk metadata 含 `product_id`。
- 前端上传商品文档不再报字段错误。

## Step 2：修复商品抓取的平台注册表

### 目标

让商品抓取逻辑支持未来多平台扩展，同时避免非拼多多平台误调用拼多多抓取器。

### 涉及文件

- `app/api/routes_products.py`
- `app/local_agent/scrapers/pdd_product_scraper.py`
- 新增：`app/local_agent/scrapers/registry.py`
- `frontend/src/components/ProductManagement.tsx`
- `tests/test_products.py` 或新增 `tests/test_product_scrape_routes.py`

### 当前问题

`routes_products.py` 的 `/api/products/scrape` 接收 `platform`，但 `_run_scrape` 硬编码使用 `PddProductScraper`。

### 实施内容

1. 新增 `app/local_agent/scrapers/registry.py`。

建议结构：

```python
from typing import Dict, Type

SUPPORTED_PRODUCT_SCRAPERS = {
    "pinduoduo": "app.local_agent.scrapers.pdd_product_scraper.PddProductScraper",
}

def get_product_scraper(platform: str):
    key = (platform or "").strip().lower()
    if key not in SUPPORTED_PRODUCT_SCRAPERS:
        return None
    # lazy import，避免 Playwright 未安装时影响普通后端启动
    module_path, class_name = SUPPORTED_PRODUCT_SCRAPERS[key].rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)

def list_supported_product_scraper_platforms() -> list[str]:
    return sorted(SUPPORTED_PRODUCT_SCRAPERS.keys())
```

2. 修改 `routes_products.py` 的 scrape 接口。

在创建任务前校验：

```python
scraper_cls = get_product_scraper(platform)
if scraper_cls is None:
    raise HTTPException(
        status_code=400,
        detail={
            "code": "platform_scraper_not_supported",
            "message": f"Product scraping is not supported for platform: {platform}",
            "supported_platforms": list_supported_product_scraper_platforms(),
        },
    )
```

3. `_run_scrape()` 中不要直接 import `PddProductScraper`。

应使用注册表获取当前平台对应 scraper。

4. 前端商品管理页：

- 如果平台不是 `pinduoduo`，禁用“平台抓取商品”按钮。
- 显示清晰文案：当前平台暂未支持商品抓取，可先用 CSV 导入。

### 测试方式

后端测试：

```powershell
$env:DEBUG='false'
D:\anaconda3\python.exe -m pytest tests\test_products.py -q
```

建议新增测试：

1. `platform=pinduoduo` 能创建抓取任务。
2. `platform=xianyu` 返回 400。
3. 返回体中有 `platform_scraper_not_supported`。

### 验收标准

- 非拼多多平台不会调用拼多多抓取器。
- 拼多多抓取任务仍可创建。
- 前端不会误导用户以为所有平台都可抓取。

## Step 3：商品列表按平台过滤

### 目标

前端切换平台时，只显示该平台商品，避免多平台数据混在一起。

### 涉及文件

- `frontend/src/components/ProductManagement.tsx`
- `app/api/routes_products.py`
- `app/storage/product_store.py`

### 后端现状

`GET /api/products` 已支持：

```text
merchant_id
platform
limit
```

但前端可能没有传 `platform`。

### 实施内容

1. 修改 `ProductManagement.tsx` 的 `loadProducts()`。

请求应包含：

```text
/api/products?merchant_id=default&platform=${selectedPlatform}&limit=200
```

2. 平台切换时重新加载商品。

React effect 应依赖：

```ts
selectedPlatform
```

3. CSV 导入后刷新当前平台商品列表。

4. 如果当前平台无商品，显示空状态，不要显示其他平台商品。

### 测试方式

1. 导入拼多多 CSV。
2. 切换到闲鱼。
3. 闲鱼页面不应显示拼多多商品。
4. 切回拼多多，商品仍在。

### 验收标准

- 商品库中可以同时存在多个平台商品。
- 前端每次只显示当前平台商品。
- CSV 导入写入的是当前选择平台。

## Step 4：当前会话商品上下文解析成 product_id

### 目标

买家在平台客服页面咨询某个商品时，系统要能把页面中的商品信息匹配到本地商品库中的 `product_id`。

这是商品文档绑定和 RAG 精准检索的前置条件。

### 涉及文件

- `app/agent/workflow.py`
- `app/storage/product_store.py`
- `app/local_agent/browser_profiles/pinduoduo_web.local.json`
- `app/local_agent/executors/browser_page.py`
- `tests/test_products.py`

### 当前能力

`workflow.py` 已能从 `page_context` 提取结构化信息，例如：

- product_name
- title
- sku
- url
- platform
- price
- stock

但还没有稳定映射到 `ProductStore` 里的商品记录。

### 实施内容

1. 在 `ProductStore` 中新增查找方法。

建议方法名：

```python
def find_by_context(
    self,
    merchant_id: str,
    platform: str | None = None,
    product_id: str | None = None,
    platform_product_id: str | None = None,
    sku: str | None = None,
    title: str | None = None,
) -> ProductRecord | None:
```

匹配优先级：

1. 本地 `product_id`
2. `platform + platform_product_id`
3. `platform + sku`
4. `platform + title` 精确匹配
5. `platform + title` 归一化包含匹配

2. 标题归一化。

建议新增内部函数：

```python
def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", "", value or "").lower()
```

3. 修改拼多多选择器配置。

确认 `pinduoduo_web.local.json` 能提取：

- 商品标题
- 平台商品 ID
- SKU 或商品编码
- 价格

如果当前只有：

```json
"sku": "p.good-id"
```

建议明确拆成：

```json
"platform_product_id": "p.good-id",
"product_name": "a.good-detail",
"price": "span.good-price"
```

同时保留 `sku` 兼容旧逻辑。

4. 修改 `workflow.py`。

在 `_structured_from_page_context()` 或后续步骤里调用 `ProductStore.find_by_context()`。

将匹配结果写入运行时上下文：

```python
structured_data["matched_product_id"] = product.id
structured_data["matched_product_title"] = product.title
structured_data["matched_product_source"] = product.source_type
```

如果没匹配到，应保留页面原始商品信息，不要报错。

### 测试方式

新增商品库单元测试：

1. 用 `platform_product_id` 匹配。
2. 用 `sku` 匹配。
3. 用标题精确匹配。
4. 用标题归一化包含匹配。
5. 不同平台同名商品不串库。

命令：

```powershell
$env:DEBUG='false'
D:\anaconda3\python.exe -m pytest tests\test_products.py -q
```

### 验收标准

- page_context 中有商品信息时，workflow 能解析出 `matched_product_id`。
- 不同平台商品不会错配。
- 匹配失败不影响普通客服回答。

## Step 5：RAG 检索支持 product_id 优先过滤

### 目标

当当前会话匹配到商品 `product_id` 时，RAG 应优先检索该商品绑定文档。

### 涉及文件

- `app/rag/retriever.py`
- `app/rag/vector_store.py`
- `app/agent/workflow.py`
- `tests/`

### 当前能力

`vector_store.py` 已有类似：

```python
similarity_search_with_product_filter(query, product_id, k, fallback_k)
```

但 `Retriever.retrieve()` 还没有暴露 `product_id` 参数，workflow 也没传。

### 实施内容

1. 修改 `Retriever.retrieve()`。

建议签名：

```python
def retrieve(
    self,
    query: str,
    k: int = 5,
    product_id: str | None = None,
) -> list[SearchResult]:
```

逻辑：

```python
if product_id:
    return self.vector_store.similarity_search_with_product_filter(
        query=query,
        product_id=product_id,
        k=k,
        fallback_k=k,
    )
return self.vector_store.similarity_search(query=query, k=k)
```

2. 修改 `workflow.py`。

在 retrieve 阶段：

```python
product_id = structured_data.get("matched_product_id") or request.product_id
search_results = retriever.retrieve(
    query,
    k=settings.similarity_top_k,
    product_id=product_id,
)
```

3. 在 debug metadata 中返回：

```python
"rag_product_filter": product_id
```

4. 如果商品专属文档没有结果，可以允许 fallback 到商家通用知识。

注意：fallback 不能无证据编造。回答质量闸门仍要生效。

### 测试方式

建议新增单元测试：

1. 有 `product_id` 时调用 product filter。
2. 无 `product_id` 时调用普通 similarity search。
3. product filter 无结果时 fallback 生效。

可通过 fake vector store 或 monkeypatch 实现。

### 验收标准

- 商品文档上传后，买家问该商品问题时优先命中该商品文档。
- 通用政策问题仍能命中通用知识。
- 不同商品文档不互相污染。

## Step 6：Local Agent 决策结果回传 UI

### 目标

平台详情页能实时看到 Local Agent 最近一次处理结果，包括：

- 最近买家消息
- 最近生成回复
- 是否允许自动发送
- 是否已真实发送
- 是否转人工
- 风险原因
- 当前 selector profile
- 当前平台和店铺状态

### 涉及文件

- `app/local_agent/runtime.py`
- `app/api/routes_local_agent.py`
- `app/api/routes_platform.py`
- `frontend/src/components/PlatformDetail.tsx`

### 当前能力

Local Agent 已有 heartbeat/status 接口，平台详情页也能轮询平台状态。

但决策结果不一定完整写回 heartbeat metadata。

### 实施内容

1. 检查 `LocalAgentRuntime` 的处理循环。

在每次读取到消息并调用后端生成回复后，应构造：

```python
decision_snapshot = {
    "latest_buyer_message": message.text,
    "latest_reply": response.reply_text,
    "auto_send_allowed": response.auto_send_allowed,
    "send_status": send_result.status,
    "risk_level": response.risk_level,
    "risk_reasons": response.risk_reasons,
    "handoff_required": response.handoff_required,
    "conversation_id": message.conversation_id,
    "platform": platform,
    "selector_profile": selector_profile_name,
}
```

2. 将该 snapshot 通过 heartbeat 上报。

3. `routes_platform.py` 聚合状态时，保留这些字段。

4. `PlatformDetail.tsx` 显示这些字段。

前端展示建议：

- 当前连接状态
- 最近买家消息
- AI 建议回复
- 自动发送状态
- 风险原因
- 最近更新时间

### 测试方式

运行：

```powershell
D:\anaconda3\python.exe -m app.local_agent.run_browser_mock --watch --interval 15 --user-data-dir data/browser_profiles/pdd_edge
```

查看：

```powershell
curl http://127.0.0.1:8000/api/platform/pinduoduo/status
```

### 验收标准

- status API 返回最新消息和最新决策。
- 前端平台详情页能看到同样信息。
- dry-run 时清楚显示未真实发送。
- 真实发送只有 `--allow-real-send` 时才可能发生。

## Step 7：清理前端乱码和旧页面状态

### 目标

让前端可以作为演示系统使用，文案清晰，不再出现明显乱码。

### 涉及文件

- `frontend/src/App.tsx`
- `frontend/src/components/ProductManagement.tsx`
- `frontend/src/components/PlatformAccess.tsx`
- `frontend/src/components/PlatformDetail.tsx`
- `frontend/src/components/MockShopWorkbench.tsx`
- `frontend/src/components/ChatInterface.tsx`

### 实施内容

1. 只清理用户可见文案，不重构业务逻辑。
2. 中文文案统一为简洁表达。
3. 平台状态建议分为：

- 未配置
- 已配置
- 浏览器已连接
- Agent 监听中
- Dry-run 中
- 自动发送中
- 需人工接管
- 异常

4. 商品管理页至少包含：

- 平台选择
- CSV 导入
- 平台抓取按钮
- 商品列表
- 商品关联文档上传
- 商品绑定状态

5. 平台详情页至少包含：

- 平台登录入口
- Local Agent 启动命令提示
- 当前状态
- 最近消息
- 最近回复
- 自动发送开关说明

### 测试方式

```powershell
cd frontend
npm run build
```

人工检查页面：

- 首页
- 商品管理
- 平台详情
- 聊天测试
- Mock 工作台

### 验收标准

- 页面没有明显乱码。
- 用户能理解当前系统能做什么、不能做什么。
- 没有把未支持平台误标为已完整支持。

## Step 8：端到端验证拼多多最小闭环

### 目标

验证系统是否已经能跑通：

商品导入或抓取 → 商品文档绑定 → 买家消息读取 → RAG 回答 → dry-run 回填 → 状态展示。

### 准备测试数据

准备一个测试商品 CSV：

```csv
platform_product_id,title,sku,price,stock,status
pdd-test-001,测试立式全身镜,pdd-sku-001,99.00,20,active
```

准备一个商品文档：

```text
测试立式全身镜采用免打孔设计，支持靠墙摆放。
镜框为金属材质。
默认发中通快递。
本商品支持 7 天无理由退货，但定制款不支持。
```

### 验证步骤

1. 启动后端。
2. 启动前端。
3. 打开商品管理页。
4. 选择拼多多。
5. 导入 CSV。
6. 确认商品出现在拼多多商品列表。
7. 给该商品上传说明文档。
8. 打开聊天测试页或 Mock 页面。
9. 构造带商品上下文的问题：

```text
这个镜子支持几天无理由退货？
```

10. 期望回答包含：

```text
支持 7 天无理由退货，定制款除外
```

11. 打开平台详情页，确认状态更新。
12. 运行拼多多 dry-run Local Agent。
13. 确认不会真实发送。

### 验收标准

- 商品能导入。
- 商品文档能绑定。
- RAG 能引用绑定文档。
- workflow 能识别当前商品。
- dry-run 不真实发送。
- 平台状态页能显示最近消息和决策。

## Step 9：真实拼多多页面小流量验证

### 前提

只有 Step 8 完整通过后，才能做真实页面验证。

### 安全要求

1. 第一次只做 dry-run。
2. 只处理最新一条消息。
3. 不使用 `--process-all-visible`。
4. 不开启 `--allow-real-send`。
5. 确认 selector 稳定后，再考虑真实发送。

### dry-run 命令

```powershell
cd D:\develop_python\system\ecommerce-agent-framework
$env:DEBUG='false'
D:\anaconda3\python.exe -m app.local_agent.run_browser_mock --watch --interval 15 --user-data-dir data/browser_profiles/pdd_edge
```

### 真实发送测试命令

只有测试低风险消息时才使用：

```powershell
D:\anaconda3\python.exe -m app.local_agent.run_browser_mock --watch --interval 15 --user-data-dir data/browser_profiles/pdd_edge --allow-real-send
```

### 验收标准

- 能读取最新买家消息。
- 能识别当前商品。
- 能生成合理回复。
- dry-run 不点击发送。
- 加 `--allow-real-send` 后，只对低风险问题真实发送。
- 高风险问题进入转人工状态。

## Step 10：阶段性整理和文档更新

每完成一个 Step，必须更新：

- `docs/EXECUTION_TRACKER.md`
- `docs/CURRENT_GOAL_AND_PROGRESS.md`
- `docs/PHASE_7_8_INTEGRATION_REPAIR_PLAN.md`
- 如有必要，更新本文件。

记录格式建议：

```markdown
### YYYY-MM-DD Step X 完成记录

- 完成内容：
  - ...
- 修改文件：
  - ...
- 验证命令：
  - ...
- 验证结果：
  - ...
- 已知遗留：
  - ...
- 下一步：
  - ...
```

## 9. 多平台扩展方案

当前只应把拼多多做扎实。其他平台先做占位，不要假装已支持。

### 9.1 平台扩展必须新增三类配置

每个平台至少需要：

1. 平台注册信息
   - `app/api/routes_platform.py`

2. 浏览器选择器配置
   - `app/local_agent/browser_profiles/{platform}_web.template.json`
   - `app/local_agent/browser_profiles/{platform}_web.local.json`

3. 商品抓取器或导入器
   - `app/local_agent/scrapers/{platform}_product_scraper.py`
   - 注册到 `app/local_agent/scrapers/registry.py`

### 9.2 多平台抽象要求

业务代码不应出现：

```python
if platform == "pinduoduo":
    ...
```

除非是在平台适配器、选择器、scraper 自身内部。

通用流程应使用：

```python
adapter = get_platform_adapter(platform)
scraper = get_product_scraper(platform)
profile = get_selector_profile(platform)
```

### 9.3 下一平台建议

完成拼多多后，建议第二个平台做闲鱼。

原因：

- 闲鱼商家客服场景较轻。
- 商品咨询和聊天窗口相对直观。
- 对毕业设计展示足够有代表性。

但不要在拼多多未闭环前并行做闲鱼。

## 10. 后续功能规划

下面是完成主链路后的功能，不要提前插队。

### 10.1 风险策略可视化配置

目标：

- 商家可配置哪些问题必须转人工。
- 例如退款、投诉、差评、平台处罚、线下交易、敏感词、超出知识库等。

建议文件：

- `app/agent/risk_policy.py`
- 新增 `app/storage/risk_policy_store.py`
- 前端新增或扩展 `ReplyStrategy` 页面。

### 10.2 问答模板沉淀

目标：

- AI 不会回答或转人工的问题，人工处理后可沉淀为模板。
- 下次类似问题优先走模板。

建议数据结构：

```json
{
  "id": "...",
  "merchant_id": "default",
  "platform": "pinduoduo",
  "product_id": "optional",
  "question_patterns": ["支持退货吗", "能退吗"],
  "answer": "亲，本商品支持 7 天无理由退货，定制款除外。",
  "source": "manual_confirmed",
  "enabled": true
}
```

### 10.3 商家数据库连接器

目标：

- 商家可以通过界面填写数据库连接信息。
- 系统读取商家的商品、库存、订单状态。

建议先做模拟数据库：

- SQLite
- CSV
- JSON

后续再做：

- MySQL
- PostgreSQL
- ERP API

### 10.4 Local Agent 管理界面

目标：

- 前端可以启动、停止、查看 Local Agent。
- 当前先不要强行实现，因为 Windows 下进程管理和浏览器 profile 容易复杂。

建议先只显示命令和状态。

### 10.5 历史对话和上下文压缩

目标：

- 保存会话历史。
- 对长会话做摘要。
- 把摘要作为后续上下文。

建议：

- 短期上下文：后端内存或 SQLite。
- 长期历史：SQLite。
- 每个平台 conversation_id 单独隔离。

## 11. 推荐实施顺序总表

必须按这个顺序推进：

1. Step 0：基线检查。
2. Step 1：修复商品关联文档上传。
3. Step 2：修复商品抓取平台注册表。
4. Step 3：商品列表按平台过滤。
5. Step 4：当前会话商品上下文解析成 product_id。
6. Step 5：RAG 检索支持 product_id 优先过滤。
7. Step 6：Local Agent 决策结果回传 UI。
8. Step 7：清理前端乱码和旧页面状态。
9. Step 8：端到端验证拼多多最小闭环。
10. Step 9：真实拼多多页面小流量验证。
11. Step 10：阶段性整理和文档更新。

不要跳过 Step 4 和 Step 5。否则商品文档绑定只是“上传成功”，并没有真正参与客服回答。

## 12. 最终验收标准

项目进入下一阶段前，至少满足以下条件：

1. 后端能启动。
2. 前端能启动。
3. 商品库可以持久化。
4. CSV 商品导入成功。
5. 商品列表按平台隔离。
6. 商品文档可以绑定 product_id。
7. RAG 能按 product_id 优先检索。
8. 拼多多页面能 dry-run 读取最新买家消息。
9. AI 回复能显示结构化风险结果。
10. 默认不真实发送。
11. 真实发送必须显式开启。
12. 高风险问题不自动发送。
13. 平台详情页能看到 Agent 最新状态。
14. 前端主要页面无明显乱码。
15. 所有改动有测试或至少有手工验证记录。

## 13. 接手者需要特别注意的坑

1. 不要直接运行单个 Python 文件，例如：

```powershell
D:\anaconda3\python.exe app\agent\workflow.py
```

这样会出现：

```text
ModuleNotFoundError: No module named 'app'
```

应该从项目根目录用模块方式运行。

2. 不要在非项目根目录启动 uvicorn。

正确方式：

```powershell
cd D:\develop_python\system\ecommerce-agent-framework
D:\anaconda3\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

3. 不要让非拼多多平台调用拼多多 scraper。

4. 不要默认真实发送。

5. 不要把历史消息全部处理。

6. 不要只做 UI 演示而不打通 product_id 到 RAG。

7. 不要把商品抓取、商品库、知识库、聊天 Agent 写成互相独立的功能。它们必须形成闭环。

8. PowerShell 里 `Get-Content` 有时会显示中文乱码，不一定代表文件本身编码错误。需要用 IDE 或 Python UTF-8 读取确认。

## 14. 建议接手者第一天只做这些事

第一天不要急着写新功能。

建议顺序：

1. 按本文档启动后端。
2. 按本文档启动前端。
3. 跑 `tests/test_products.py`。
4. 打开商品管理页，看当前商品列表。
5. 看 `ProductManagement.tsx` 商品文档上传字段名。
6. 看 `routes_knowledge.py` 的 product_id 传递。
7. 看 `routes_products.py` 的 scrape 硬编码。
8. 完成 Step 1 和 Step 2。
9. 更新执行文档。

第一天验收：

- 商品文档上传字段修好。
- 非拼多多平台不会误触发拼多多抓取。
- 测试和前端 build 通过。

## 15. 最重要的判断标准

这个项目不是单纯“做很多页面”。真正有价值的闭环是：

```text
平台消息
  -> 当前商品上下文
  -> 本地商品库匹配 product_id
  -> product_id 绑定知识库
  -> RAG 精准检索
  -> 风险策略判断
  -> 自动发送或转人工
  -> 状态回传 UI
```

后续所有开发都应围绕这条链路推进。
