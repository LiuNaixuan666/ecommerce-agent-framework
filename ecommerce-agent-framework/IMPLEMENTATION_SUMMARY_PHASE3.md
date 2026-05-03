# Phase 3 Implementation Summary

## 1. 目标

本阶段目标是将项目从“Mock 组件+演示实现”升级为更接近真实生产流程的架构：

- 将 `MockIntentParser` 替换为真实的 `IntentParser`，并保持降级容错能力
- 将“模拟 embeddings”切换为真实 `OpenAIEmbeddings`，同时支持本地文本向量降级
- 完善结构化适配器逻辑，补齐 `ORDER_SERVICE` 和 `POLICY_INQUIRY` 情况
- 添加针对适配器方法的单元测试
- 增加真实平台适配器骨架：Taobao、JD、Amazon、ERP

## 2. 主要变更文件

- `app/api/routes_chat.py`
- `app/connectors/base.py`
- `app/connectors/__init__.py`
- `tests/test_connectors.py`
- `IMPLEMENTATION_SUMMARY_PHASE3.md`

## 3. `routes_chat.py` 具体改动

### 3.1 IntentParser 实际集成

- 保留了原有的 `IntentParser` 真实调用路径。
- 当 `OPENAI_API_KEY` 有效时，`IntentParser` 使用 OpenAI 进行真实意图解码。
- 当 IntentParser 初始化或 API 调用失败时，仍使用关键词型降级解析器，保证服务可用。

### 3.2 Embeddings 集成与降级策略

- 增加对 `OpenAIEmbeddings` 的引入，优先使用真实 OpenAI embeddings。
- 当 `OPENAI_API_KEY` 未配置或实例化失败时，自动切换到 `LocalTextEmbeddings`：
  - 使用简单文本分词+哈希向量化
  - 提供 `embed_documents` / `embed_query` 接口
  - 保证向量检索功能仍可运行
- 向量检索结果统一执行距离到相似度的转换：`1.0 / (1.0 + distance)`。

### 3.3 结构化检索增强

- 完善 `retrieve_knowledge()` 的结构化调用范围，支持：
  - `PRODUCT_INQUIRY`
  - `ORDER_SERVICE`
  - `POLICY_INQUIRY`
- 使结构化结果在 `structured_data` 返回时能够持续进入后续生成流程。
- `POLICY_INQUIRY` 也能通过结构化适配器命中并作为主检索信号。

### 3.4 混合检索与检索类型区分

- 当仅结构化数据命中时，`retrieval_type` 标记为 `structured`。
- 当同时存在结构化数据与向量文档时，标记为 `hybrid`。
- 当仅向量检索命中时，标记为 `rag`。

## 4. 结构化适配器与平台适配器

### 4.1 `MockMerchantAdapter` 增强

- `get_order_status()` 已经支持订单状态查询。
- `get_shipping_info()` 已经支持订单物流信息查询。
- `get_policy()` 已经支持退货、运费、保修和退款等政策查询。

### 4.2 真实平台适配器骨架

在 `app/connectors/base.py` 中新增：

- `TaobaoAdapter`
- `JDAdapter`
- `AmazonAdapter`
- `ERPAdapter`

每个类都实现了 `MerchantDataAdapter` 接口方法，并且为真实 API 集成预留了明确的 `NotImplementedError` 插口。

### 4.3 平台适配器工厂

- 添加了 `get_platform_adapter(platform_name)` 工厂函数。
- 支持按平台名称切换适配器，实现后期真实平台接入更方便。

## 5. 测试覆盖

新增测试文件：

- `tests/test_connectors.py`

覆盖内容：

- `MockMerchantAdapter` 的商品价格与库存查询
- `MockMerchantAdapter` 的订单状态与物流查询
- `MockMerchantAdapter` 的政策信息查询
- 平台适配器工厂返回正确骨架类

现有 `tests/test_ingestion.py` 继续覆盖向量库接入逻辑。

## 6. 运行建议

### 6.1 环境依赖

- `OPENAI_API_KEY` 若可用，则系统会自动使用真实 OpenAI embeddings 和意图解析。
- 若不可用，系统会自动降级：
  - IntentParser 使用关键词降级解析
  - Embeddings 使用 `LocalTextEmbeddings` 本地向量降级
  - 回答生成在 OpenAI API 不可用时也会退回本地模板生成

### 6.2 推荐测试命令

```bash
cd d:/develop_python/system/ecommerce-agent-framework
pytest tests/test_connectors.py tests/test_ingestion.py
```

## 7. 后续建议

- Phase 4 可以继续落地真实平台适配器：
  - 使用淘宝/京东/亚马逊/ERP 的官方 SDK 或开放 API
  - 将 `get_platform_adapter` 工厂与 `routes_chat.py` 中的结构化查询绑定
  - 为真实平台添加认证与请求缓存机制
- 补齐更完整的 `routes_chat` 单元测试，覆盖真实 `retrieve_knowledge()` 逻辑和 `generate_grounded_response()` 模板
- 将本地向量降级替换为更强的本地 embedding 模型（例如 `sentence-transformers` 或 `HuggingFaceEmbeddings`）
