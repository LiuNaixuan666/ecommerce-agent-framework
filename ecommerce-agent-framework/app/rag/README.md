# RAG 层架构说明

本说明文档总结了 `app/rag` 目录中各文件的职责，以及 `engine.initialize()` 在应用启动时触发的作用。

## RAG 层整体作用

RAG（Retrieval-Augmented Generation）是一种将检索与生成结合的架构。对于电商智能客服系统，RAG 的主要目标是：

1. 从商家知识库中检索相关信息（知识检索）
2. 将检索到的信息作为上下文交给 LLM 进行回答生成
3. 保证回答基于真实资料，降低 hallucination 风险

在这个项目中，RAG 层负责“存储、检索、评分、重排序”与“生成上下文准备”的核心工作。

## 目录与文件职责

### `app/rag/vector_store.py`
- 作用：管理本地 Chroma 向量库
- 功能：
  - 为每个商家创建独立持久化目录
  - 统一 Chroma 配置和 collection 命名
  - 提供 `VectorStore` 包装器，封装 `similarity_search_with_score`
- 价值：保证不同商家数据隔离，避免检索串库。

### `app/rag/embedder.py`
- 作用：统一向量化接口
- 功能：
  - 调用 `app.embeddings.factory.get_embedding_client()`
  - 提供 `embed_documents(texts)` 和 `embed_query(text)` 方法
- 价值：将 embedding 逻辑从检索层抽象出来，后续可以插入 Gemini、Claude、千问等不同 provider。

### `app/rag/retriever.py`
- 作用：实现检索器核心逻辑
- 功能：
  - 使用 `Embedder` 获取向量化能力
  - 通过 `VectorStore` 执行相似度搜索
  - 返回统一格式的文档结果和相似度分数
- 价值：将向量检索从应用业务代码中剥离出来，形成可复用、可测试的组件。

### `app/rag/reranker.py`
- 作用：检索后处理层
- 功能：
  - 提供 `rerank(results, query)` 扩展点
  - 当前版本作为透传器保留
- 价值：未来可以在此处加入语义重排序、规则过滤、降噪、意图优先顺序等策略。

### `app/rag/__init__.py`
- 作用：包初始化入口
- 功能：现在是空文件，但保留为 Python 包入口，便于后续统一导出组件。

## `app/engine.py` 的作用

`engine.py` 不是单纯的业务实现，而是“系统引擎”：

- 初始化全局组件
- 负责管理意图解析、检索器、向量库、生成器和适配器
- 提供统一的 getter 方法

它的关键作用是：

- 将 RAG 组件集中管理
- 在应用启动时完成商家 retriever 注册，避免每次请求动态创建
- 让上层 API 或工作流只需调用 `engine.get_retriever(merchant_id)` 即可

## 为什么要把 `engine.initialize()` 放到应用启动事件里？

### 1. 提前检测错误

如果启动时就执行 `engine.initialize()`，可以在服务启动阶段就发现配置、依赖或商家目录问题，而不是等到第一条请求时才报错。

### 2. 预热检索器

`engine.initialize()` 会为每个商家创建：
- `Embedder`
- `VectorStore`
- `Retriever`

这意味着当用户发送第一条聊天请求时，检索器已准备好，响应路径更短，启动延迟更低。

### 3. 避免重复初始化

如果不在启动时初始化，每次请求可能都要检查或创建 retriever，导致：
- 代码复杂
- 资源浪费
- 性能抖动

而在启动时初始化，则可以把这些开销固定到服务启动阶段。

## 具体效果

当 FastAPI 应用启动时：

- `engine.initialize()` 读取 `data/merchants/` 下的商家目录
- 为每个商家生成对应 `Retriever`
- 将这些检索器缓存到 `engine.retrievers`

后续聊天请求在 `app/api/routes_chat.py` 中：

- 直接调用 `engine.get_retriever(merchant_id)`
- 只需执行相似度检索和 rerank
- 不再创建 embedding client、vector store 等底层对象

## 你现在可以期待的架构路径

- `app/embeddings/`：可插拔 embedding provider
- `app/llm/`：可插拔生成 provider
- `app/rag/`：负责检索与结果排序
- `app/engine.py`：负责组件初始化与全局管理
- `app/api/routes_chat.py`：负责业务流程编排

## 未来扩展建议

1. 把 `Reranker` 实现为 `semantic rerank` 或 `intent-aware rerank`
2. 为 `app/rag/retriever.py` 添加 `hybrid_retrieve()`，同时支持结构化数据与向量检索
3. 把 `app/rag/__init__.py` 做成统一导出入口，方便外部模块直接 `from app.rag import Retriever`
4. 将 `engine.initialize()` 的商家列表和 retriever 注册状态导出为健康检查信息

---

**总结：**

`app/rag` 负责“存储、向量化、检索、重排序”；
`engine.initialize()` 则负责“系统启动时预热、注册和管理这些组件”，使整个系统更稳、更快、更易扩展。





让 engine.initialize() 在应用启动时触发
已修改：

app/main.py
新增内容：

@app.on_event("startup")
启动时调用 engine.initialize()
启动失败时记录日志
健康检查 /health 会显示 initializing 或 healthy
3. 这样做的意义
把 engine.initialize() 放到应用启动事件里，主要是为了：

提前检测问题：如配置、商家目录、模型依赖等，启动时就会发现
预热检索器：在请求来之前，就已为每个商家创建好 Retriever
降低请求延迟：用户请求时不再重复初始化 retriever/embedding
减少运行时开销：避免每次请求都创建底层组件
4. 现在你可以做的
查看 app/rag/README.md
继续补齐 app/knowledge、app/api/routes_knowledge.py
继续加上 app/llm 其它 provider
如果你愿意，我也可以继续帮你把这个说明内容同步写进 FILES_REFERENCE.md 或 前后端整体架构梳理.md。