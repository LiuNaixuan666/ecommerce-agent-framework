# API and Routing Construction Plan

## TL;
�
当前项目已经实现了核心业务模块（意图解析、不确定性检测、RAG 设计），但 API 层仍是框架型占位。现在最重要的是完成 `app/api/routes_chat.py` 的端到端工作流接线，并补齐 FastAPI 入口和基础路由。

## Steps
1. 先把最小可用 API 入口做出来：
   - 实现 `app/main.py`，创建 `FastAPI()` 应用并 `include_router(app.api.routes_chat.router)`。
   - 可选同时添加 `routes_knowledge` 和 `routes_evaluation` 的空路由注册。
2. 完成 `app/api/routes_chat.py` 的核心逻辑：
   - 导入 `IntentParser`、`UncertaintyDetector`、`build_clarification_prompt`。
   - 用 `IntentParser.parse()` 解析 `user_query`，得到 `intent_label` 和 `confidence_score`。
   - 设计 `IntentParser.get_retrieval_source()` 或简单映射，决定检索类型（产品、政策、订单、闲聊、其他）。
   - 实现 `retrieve_knowledge()`，调用向量检索/混合检索逻辑，返回文档片段和分数。
   - 使用 `UncertaintyDetector.detect()` 做决策：
     - 若 `is_uncertain` 且 `recommendation` 指向澄清，则返回 `ChatResponse` 中 `response_text` 为澄清提示。x 
     - 否则调用 `generate_grounded_response()` 生成最终文本。
3. 实现检索层：
   - 在 `app/rag/retriever.py` 中补齐检索接口，或直接在 `routes_chat.py` 中构建 helper。
   - 读取本地向量库 / merchant 文档；若你当前没有数据库，可先用 `vector_store.get_or_create_chroma()` 绑定 `merchant_id`。
   - 对于价格/库存问题，先做关键词分支：若 query 包含 `价格/库存/有货吗`，可进入精确查询路径；其余走向语义检索。
4. 实现响应生成层：
   - `generate_grounded_response()` 应把检索结果拼成 prompt，并调用 OpenAI LLM 生成；注意要求“引用来源、避免造假”。
   - 可以把这个逻辑拆到 `app/agent/response_generator.py`。
5. 补齐评估与知识路由：
   - `app/api/routes_knowledge.py` 可先做 `POST /api/knowledge/ingest`、`GET /api/knowledge/metadata`。
   - `app/api/routes_evaluation.py` 可先做 `POST /api/evaluation/run` 或 `GET /api/evaluation/status`。
6. 写 API 测试：
   - 使用 FastAPI `TestClient` 直接测试 `routes_chat.py` 返回结构。
   - mock `IntentParser`、`retrieve_knowledge()`、`generate_grounded_response()`，验证不同分支。
   - 保持现有 `tests/test_e2e_workflow.py` 不变，先保证它仍通过。

## Relevant files
- `app/api/routes_chat.py`
- `app/main.py`
- `app/api/routes_evaluation.py`
- `app/api/routes_knowledge.py`
- `app/agent/intent_parser.py`
- `app/agent/uncertainty_detector.py`
- `app/rag/vector_store.py`
- `PRICE_INVENTORY_DESIGN.md`

## Verification
1. 启动服务并调用 `POST /api/chat/query`，确认返回不再是 demo 文本，而是基于 intent+检索+生成的结果。
2. 为 `routes_chat.py` 添加至少 3 个测试：
   - 置信问答分支正常生成
   - 检索不足触发澄清
   - 价格/库存关键字分支（如果你实现了）
3. 运行 `pytest tests/ -q`，确保当前已有测试仍然通过。

## Status 发现
- `app/api/routes_chat.py` 是当前 API 的唯一实质文件，但里面多数业务逻辑仍为注释 TODO。
- `app/main.py`、`app/rag/retriever.py`、`app/agent/response_generator.py` 目前是空壳，意味着你需要先补全运行入口和检索/生成层。
- `routes_evaluation.py`、`routes_knowledge.py` 目前为空，属于后续可扩展接口，不必优先于 `chat/query`。

## 建议顺序
1. 先完成 `chat/query` 的端到端可运行版本。
2. 再补 `main.py` 和服务启动入口。
3. 最后再扩展 `knowledge`/`evaluation` 和价格库存混合路由。

## Further Consideration
- 你现在最需要的是“把现有功能接成一个服务”，而不是再设计新协议。
- 如果你愿意，我可以继续给你写出 `routes_chat.py` 的具体字段与数据流逻辑。

## 结构化数据适配器设计
对于你这种面向商户、面向平台的智能客服，建议把“是否从结构化系统获取数据”做成一层适配器，而不是把所有平台数据都搬到一个新数据库。关键设计如下：

1. 路由层只负责“判断问题类型”和“选择数据来源”：
   - 如果问题是“库存、价格、订单状态、发货时间、发票”等实时结构化信息，走结构化数据适配器。
   - 如果问题是“退货政策、商品说明、FAQ、商家公告”等文档知识，走 RAG 文档检索。
   - 如果两个都需要，先查询结构化数据，再用 RAG 补充解释。

2. 设计统一适配器接口：
\`\`\`python
class MerchantDataAdapter(Protocol):
    def get_product_price(self, merchant_id: str, product_id: str) -> dict: ...    def get_inventory(self, merchant_id: str, product_id: str) -> dict: ...
    def get_order_status(self, merchant_id: str, order_id: str) -> dict: ...
    def get_shipping_info(self, merchant_id: str, order_id: str) -> dict: ...
\`\`\`


3. 每种平台或系统都实现自己的适配器：
   - `TaobaoAdapter` / `JDAdapter` / `AmazonAdapter`
   - `ERPAdapter` / `WMSAdapter` / `ShopifyAdapter`
   - `MockAdapter`（开发与测试用）

4. 适配器应只负责“读取已有系统数据”，不负责生成回答。回答由你的聊天服务负责组合：
   - 结构化结果 + 说明性文本
   - 或 RAG 检索结果 + 来源引用

5. 如果没有真实平台接口，可先模拟一个适配器：
   - 用本地 SQLite、CSV、JSON 或内存数据
   - 仍然保持接口一致性，后面换成真实 adapter 时无需改核心逻辑
## 为什么不建议让 AI 直接去“获取库存/价格”
- 这类问题要求实时性，单纯靠 LLM 检索或生成会比较慢。
- LLM 不能保证精确数据，容易出现“口胡”“编造”。
- 你应该把 AI 用在“理解问题”和“生成自然语言表达”上，而不是让它当实时数据源。

因此建议的流程是：
- IntentParser 识别问题类型和关键实体。
- Router 决定是否调用 `DataAdapter`。
- 如果是结构化问题，直接返回结果或把结果送给生成层。
- 如果是文档问题，走 RAG 检索。
- 生成层把两者组合成最终回答。

## 这部分可以如何接入你当前项目
你目前已有的模块可以补成两条路径：
1. `routes_chat.py` 里保留现有意图解析 + 不确定性检测。
2. 增加一个 `StructuredQueryService` 或 `AdapterManager`。
3. `retrieve_knowledge()`可以扩展成“混合检索”：
   - 优先查询结构化适配器。
   - 如果适配器未命中，再走向量检索。
4. `response_generator` 生成的文本可包含：
   - “查询到当前价格为 XX 元”。
   - “库存剩余 10 件”。
   - “同时你也可以参考以下商品说明”。

## skill 是什么，它对你这个项目有没有价值
你同学说的 skill，本质上是“给 AI 的一个能力模块”。在很多 AI agent 框架里，skill 代表：
- 一段可复用的能力（比如写邮件、查日程、查询库存）。
- 一个对外接口或 action（比如 `send_email()`、`lookup_order()`）。
- 一组 Prompt + 处理逻辑的封装。

### 这和你的项目有什么关系？
- 如果你把 `routes_chat.py` 设计成“agent/skill”架构，确实可以提高可维护性。
- 例如你可以把 `InventoryLookupSkill`、`OrderStatusSkill`、`PolicySearchSkill`、`ClarificationSkill` 抽象出来。
- 这样你的路由层就是“意图到 skill 的映射”，每个 skill 独立实现具体逻辑。

### 但你现在不一定必须马上加这个
对于你的项目当前阶段，我建议先做：
- 核心路由 + 结构化适配器 + RAG 检索。
- 再根据需要把重要能力抽成 skill。


### 简单的演进路线
1. 先实现 `MerchantDataAdapter` / `MockAdapter`。
2. 再把结构化查询逻辑封装成 `InventorySkill`、`PriceSkill`、`OrderSkill`。
3. 最后让 `routes_chat.py` 的路由逻辑变成“意图 → skill → 结果”。

---

如果你愿意，我也可以继续帮你把这份设计直接转成 `docs/` 里的架构说明，或者把 `routes_chat.py` 改成“skill + adapter”的具体模板。
'@









我已整理出详细计划，接下来把它写成项目中的 Markdown 文件。

搜索匹配 `**/API_ROUTING_PLAN.md` 的文件，无匹配项

搜索与 `**/*.md` 匹配的文件，12 匹配项

我找到了仓库的 Markdown 文件位置，准备把计划写入根目录的新文件。

已创建记忆文件 [](file:///c%3A/Users/liu/AppData/Roaming/Code/User/workspaceStorage/6173a7af57d991d66a6d9ee800c9abfe/GitHub.copilot-chat/memory-tool/memories/N2VmZTk2MGMtMDY0OC00NTE3LTg1YzEtMDc2M2JhMzFkN2Q2/plan.md)

我现在直接把计划写入仓库根目录的 Markdown 文件。

已创建记忆文件 [](file:///c%3A/Users/liu/AppData/Roaming/Code/User/workspaceStorage/6173a7af57d991d66a6d9ee800c9abfe/GitHub.copilot-chat/memory-tool/memories/N2VmZTk2MGMtMDY0OC00NTE3LTg1YzEtMDc2M2JhMzFkN2Q2/plan.md)

搜索匹配 `system` · `ecommerce-agent-framework/API_ROUTING_PLAN.md` 的文件，无匹配项

读取 [](file:///d%3A/develop_python/system/ecommerce-agent-framework/app/main.py)

我已经整理好完整计划，建议你在仓库根目录创建一个文件 `API_ROUTING_PLAN.md`，内容如下：

---
# API and Routing Construction Plan

## TL;DR
当前项目已经实现了核心业务模块（意图解析、不确定性检测、RAG 设计），但 API 层仍是框架型占位。现在最重要的是完成 `app/api/routes_chat.py` 的端到端工作流接线，并补齐 FastAPI 入口和基础路由。

## Steps
1. 先把最小可用 API 入口做出来：
   - 实现 `app/main.py`，创建 `FastAPI()` 应用并 `include_router(app.api.routes_chat.router)`。
   - 可选同时添加 `routes_knowledge` 和 `routes_evaluation` 的空路由注册。
2. 完成 `app/api/routes_chat.py` 的核心逻辑：
   - 导入 `IntentParser`、`UncertaintyDetector`、`build_clarification_prompt`。
   - 用 `IntentParser.parse()` 解析 `user_query`，得到 `intent_label` 和 `confidence_score`。
   - 设计 `IntentParser.get_retrieval_source()` 或简单映射，决定检索类型（产品、政策、订单、闲聊、其他）。
   - 实现 `retrieve_knowledge()`，调用向量检索/混合检索逻辑，返回文档片段和分数。
   - 使用 `UncertaintyDetector.detect()` 做决策：
     - 若 `is_uncertain` 且 `recommendation` 指向澄清，则返回 `ChatResponse` 中 `response_text` 为澄清提示。
     - 否则调用 `generate_grounded_response()` 生成最终文本。
3. 实现检索层：
   - 在 `app/rag/retriever.py` 中补齐检索接口，或直接在 routes_chat.py 中构建 helper。
   - 读取本地向量库 / merchant 文档；若你当前没有数据库，可先用 `vector_store.get_or_create_chroma()` 绑定 `merchant_id`。
   - 对于价格/库存问题，先做关键词分支：若 query 包含 `价格/库存/有货吗`，可进入精确查询路径；其余走向语义检索。
4. 实现响应生成层：
   - `generate_grounded_response()` 应把检索结果拼成 prompt，并调用 OpenAI LLM 生成；注意要求“引用来源、避免造假”。
   - 可以把这个逻辑拆到 `app/agent/response_generator.py`。
5. 补齐评估与知识路由：
   - `app/api/routes_knowledge.py` 可先做 `POST /api/knowledge/ingest`、`GET /api/knowledge/metadata`。
   - `app/api/routes_evaluation.py` 可先做 `POST /api/evaluation/run` 或 `GET /api/evaluation/status`。
6. 写 API 测试：
   - 使用 FastAPI `TestClient` 直接测试 routes_chat.py 返回结构。
   - mock `IntentParser`、`retrieve_knowledge()`、`generate_grounded_response()`，验证不同分支。
   - 保持现有 `tests/test_e2e_workflow.py` 不变，先保证它仍通过。

## Relevant files
- `app/api/routes_chat.py`
- `app/main.py`
- `app/api/routes_evaluation.py`
- `app/api/routes_knowledge.py`
- `app/agent/intent_parser.py`
- `app/agent/uncertainty_detector.py`
- `app/rag/vector_store.py`
- PRICE_INVENTORY_DESIGN.md

## Verification
1. 启动服务并调用 `POST /api/chat/query`，确认返回不再是 demo 文本，而是基于 intent+检索+生成的结果。
2. 为 routes_chat.py 添加至少 3 个测试：
   - 置信问答分支正常生成
   - 检索不足触发澄清
   - 价格/库存关键字分支（如果你实现了）
3. 运行 `pytest tests/ -q`，确保当前已有测试仍然通过。

## Status 发现
- `app/api/routes_chat.py` 是当前 API 的唯一实质文件，但里面多数业务逻辑仍为注释 TODO。
- `app/main.py`、`app/rag/retriever.py`、`app/agent/response_generator.py` 目前是空壳，意味着你需要先补全运行入口和检索/生成层。
- routes_evaluation.py、routes_knowledge.py 目前为空，属于后续可扩展接口，不必优先于 `chat/query`。

## 建议顺序
1. 先完成 `chat/query` 的端到端可运行版本。
2. 再补 main.py 和服务启动入口。
3. 最后再扩展 `knowledge`/`evaluation` 和价格库存混合路由。

---

如果你希望，我也可以继续把这份内容改成更适合直接写入 `docs/` 的版本。## 建议顺序
1. 先完成 `chat/query` 的端到端可运行版本。
2. 再补 main.py 和服务启动入口。
3. 最后再扩展 `knowledge`/`evaluation` 和价格库存混合路由。

---

如果你希望，我也可以继续把这份内容改成更适合直接写入 `docs/` 的版本。







## 你的问题本质

你不需要也不应该“重建整个 SQL 数据库”。正确的做法是：

- 把“数据源访问”做成一个抽象层
- 让路由层只负责“判断这个问题是不是需要实时结构化数据”
- 实际数据由不同的连接器（connector/adapter）去适配商户已有系统

---

## 推荐架构

### 1. 路由层：先判断问题类型
`chat/query` 入口先做这件事：

- `IntentParser` 判断这是：
  - 产品/价格/库存类问题
  - 订单类问题
  - 政策/售后/FAQ类问题
  - 闲聊或其他
- 进一步做实体抽取：
  - 书名、商品名、SKU、订单号、商家 ID 等

### 2. 决策：结构化数据路径 vs RAG 路径
根据意图和实体决定：

- 如果是“库存/价格/订单状态/发货时间”等，需要**实时结构化信息**
  - 走“结构化数据访问”路径
- 如果是“退货政策、物流说明、商品详情、商家 FAQ”等
  - 走“RAG + 文档检索”路径
- 如果两个都有可能，则先查结构化数据，再补充文档解释

---

## 关键设计：适配器/连接器模式

你应该做一个统一接口，比如：

```python
class MerchantDataAdapter(Protocol):
    def get_product_price(self, merchant_id: str, product_id: str) -> dict: ...
    def get_inventory(self, merchant_id: str, product_id: str) -> dict: ...
    def get_order_status(self, merchant_id: str, order_id: str) -> dict: ...
```

每个商户/平台实现不同适配器：

- TaobaoAdapter
- JDAdapter
- AmazonAdapter
- ERPAdapter
- MockAdapter（开发/测试用）

这样你就不用重建数据库，而是把商户已有系统“映射成你自己的查询接口”。

---

## 不建议的做法

### 1. 不建议用 AI 来直接获取库存/价格
如果把“库存/价格”问题交给 LLM 直接回答，会有两个问题：

- 速度慢
- 容错差，容易“编造”数据
- 不能保证实时性

所以这类问题应当由结构化系统直接回答，LLM 只负责：
- 理解用户意图
- 生成自然语言回应
- 在必要时解释数据来源

### 2. 也不建议把所有问题都交给一个“泛用 SQL”
如果你只是想做商户级智能客服，不必把淘宝/JD/Amazon 的数据库结构都统一成一个新库。那会很复杂，而且没必要。

---

## 如果真实平台接口暂时拿不到，怎么办？

### 最好方式
先做“抽象接口 + Mock 实现”，例如：

- `MerchantAdapter` 接口
- `MockMerchantAdapter` 用本地 CSV/SQLite/JSON 模拟
- 业务代码只依赖接口，不依赖具体实现

这意味着以后你有真实店铺系统时，只要换成 `TaobaoAdapter` / `ERPAdapter` 即可。

### 何时需要模拟
- 真实平台 API 不可得
- 你现在做的是 POC/demo
- 你需要先验证路由和整体架构

所以“模拟数据库”是合理的开发手段，但最终目标应是“可替换的实际数据源”。

---

## 具体建议给你项目

### 在 routes_chat.py 里
把逻辑分成三层：
1. `IntentParser`：判断问题类型
2. `Router`：如果是结构化问题，调用 `StructuredQueryService`
3. `ResponseGenerator`：把结构化结果和文档结果拼成最终回答

### 新增一个 `data_adapter` 或 `connectors` 目录
例如：

- `app/connectors/base.py`
- `app/connectors/taobao.py`
- `app/connectors/jd.py`
- `app/connectors/amazon.py`
- `app/connectors/mock.py`

### 设计一个 “混合检索” 入口
```text
用户问题 -> 意图解析
   -> 结构化数据查询
   -> 如果未命中或需要补充 -> RAG 文档检索
```

---

## 你现在应该怎么做

1. 先把“结构化数据适配器”抽象出来
2. 先实现一个 mock 适配器用于本地开发
3. 把路由逻辑改成：
   - 结构化问题走 adapter
   - 其他问题走 RAG
4. 以后有真实平台时，补真实 adapter，不用改核心逻辑

---

## 结论

- 你不必重建 SQL 数据库
- 应该做“接口层 + 适配层”
- 结构化数据用“连接器/适配器”访问
- LL M 主要用来理解问题、生成回答、不当做实时数据源
- 如果不能接真实系统，先模拟；但务必保持替换性

如果你愿意，我可以直接帮你把这个设计写成一份 `API_ROUTING_DESIGN.md` 或者补充到 `planApiRouting.prompt.md` 里。