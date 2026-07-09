# 项目概述：E-commerce Agent Framework

## 1. 项目名称

E-commerce Agent Framework

## 2. 项目定位

这是一个面向电商客服与商家助手的智能对话 PoC 框架。

它整合了：
- 浏览器扩展页面上下文抽取
- FastAPI 本地后端服务
- 知识库文档上传与 RAG 摄取
- 多平台消息适配器（轮询 / webhook / 适配器工厂）
- LLM 回答生成与不确定性守门员
- Redis / PostgreSQL 存储选项

目标是构建一个可以验证“商家本地插件 + 本地 AI 服务 + 多平台接入”的电商客服解决方案。

## 3. 项目组件与功能

### 3.1 浏览器扩展 PoC

`browser_extension` 目录内的扩展实现了：
- `content_script.js` 自动提取商品页面中的标题、价格、库存、SKU 和页面 URL
- 支持 Taobao/天猫、JD 两大电商平台的 DOM 规则，以及通用商品页提取
- 将提取到的页面上下文发送到本地接口 `POST /api/extension/page-context`
- `popup.html` + `popup.js` 提供用户问答入口，将用户提问与页面上下文一起发送到 `POST /api/extension/page-chat`

该扩展用于演示“页面层上下文”如何与后端 RAG/回答生成结合。

### 3.2 FastAPI 后端接口

当前主要接口如下：

#### 聊天与扩展接口
- `POST /api/chat/query`：端到端聊天入口，支持多轮会话、意图解析、检索和不确定性判定
- `POST /api/chat/webhook/{platform}`：通用第三方平台 webhook 入口，将事件转交给 `ChatManager` 处理
- `POST /api/extension/page-context`：接收浏览器扩展页面上下文
- `POST /api/extension/page-chat`：基于扩展页面上下文和用户问题生成回答

#### 知识库与摄取接口
- `POST /api/knowledge/upload`：商家上传知识文档
- `GET /api/knowledge/status/{upload_id}`：查询摄取任务状态
- `POST /api/knowledge/ingest`：手动触发摄取
- `GET /api/knowledge/list-uploads`：列出上传任务
- `GET /api/knowledge/health`：知识模块健康检查

### 3.3 RAG 与知识摄取

项目实现了一个文档上传与摄取流程：
- 商家上传 `.txt`、`.pdf`、`.docx`、`.csv`、`.md` 等文档
- 上传文件先保存到临时 staging 目录
- 后台任务搬运文件到 `data/merchants/<merchant_id>/raw_docs`
- 调用 `ingest_merchant_documents()` 进行文本切分、向量索引构建
- 摄取任务状态记录在 `storage_manager` 中，可通过 API 查询

这意味着项目不仅仅是“页面上下文+问答”，还具备文档 RAG 检索能力。

### 3.4 商家隔离与多商家支持

商家隔离通过以下方式实现：
- `data/merchants/<merchant_id>/raw_docs` 存放该商家的原始文档
- 每个商家单独初始化 `VectorStore`、`Retriever` 和 `MerchantDataAdapter`
- `Engine._get_merchant_ids()` 会扫描 `data/merchants` 下的商家目录
- `storage_manager` 可以按 `merchant_id` 过滤摄取任务

因此系统设计为“每个商家独立知识库 / 会话上下文”的架构。

### 3.5 多平台适配器与 webhook

项目中存在两类适配器：

#### `ChatAdapter` / `ChatAdapterFactory`
- 定义统一的聊天适配器协议
- 可以动态创建平台 adapter
- 目前主要实现了 `xiaohongshu_adapter`，并支持 webhook 验证、轮询监听、消息解析

#### `MerchantDataAdapter` 及平台骨架
- `app/connectors/base.py` 提供 `TaobaoAdapter`、`JDAdapter`、`AmazonAdapter`、`ERPAdapter` stub
- 这些骨架目前是接口预留，用于后续真实平台接入
- `MockMerchantAdapter` 提供开发测试 mock 数据

#### `ChatManager` 功能
- 管理多个平台 adapter 实例
- 维护消息队列、会话缓存、消息入库
- 支持 `polling`、`webhook` 和 `both` 模式
- webhook 事件可直接通过 `POST /api/chat/webhook/{platform}` 进入系统

### 3.6 意图识别与 agent 流程

项目的智能对话流程包含：

1. 意图解析：`IntentParser.parse()` 使用 LLM 识别用户意图（如 `PRODUCT_INQUIRY`, `POLICY_INQUIRY`, `ORDER_SERVICE`, `CHITCHAT` 等）
2. 检索：`retrieve_knowledge()` 组合结构化数据与 RAG 检索结果
3. 不确定性检测：`UncertaintyDetector.detect()` 评估检索置信度、查询歧义、意图置信度、LLM 自评
4. 反馈判断：如果不确定，则触发澄清流程；否则调用 `ResponseGenerator` 生成回答
5. 结果存储：会话和消息历史写入 `storage_manager`

这个流程体现了“Agent + RAG + uncertainty gatekeeper”的设计。

### 3.7 存储层实现

`storage_manager` 决定了当前存储策略：
- `MemorySessionStorage`：默认内存回退
- `RedisStorage`：用于会话与消息持久化，支持过期 TTL
- `PostgresStorage`：用于摄取任务、商家信息、会话元数据的持久化

当前实现逻辑：
- 如果 `SESSION_STORAGE=redis` 且 Redis 可用，则会话存储走 Redis
- 如果 `INGESTION_STORAGE=postgres` 且 PostgreSQL 可用，则摄取任务和元数据走 PostgreSQL
- 否则回落到内存版本

因此 PostgreSQL 已经作为“历史任务 / 会话元数据存储”路径存在，但不一定是默认启用。

## 4. 技术栈与环境要求

### 4.1 后端组件

- Python 3.11+
- FastAPI
- Uvicorn
- aiohttp
- SQLAlchemy
- redis-py
- pydantic / pydantic-settings
- PostgreSQL（可选，用于 `PostgresStorage`）
- Redis（可选，用于对话会话持久化）

### 4.2 浏览器扩展

- Chrome / Edge / Chromium
- Manifest V3
- `content_script.js` 注入页面进行 DOM 抽取
- `popup.js` 实现用户提问发送逻辑

### 4.3 运行环境说明

- 可在 Windows 本地运行
- 推荐使用虚拟环境
- 如需 Redis 持久化，配置 `REDIS_HOST`, `REDIS_PORT`, `SESSION_STORAGE=redis`
- 如需 PostgreSQL 持久化，配置 `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `INGESTION_STORAGE=postgres`
- 默认可以直接运行 `uvicorn app.main:app --reload`

## 5. 关键页面与模块功能说明

### 5.1 浏览器扩展

`content_script.js`：
- 读取当前页面 URL 与域名
- 根据域名匹配 Taobao/天猫、JD 或通用规则
- 提取 `product_name`, `price`, `stock`, `sku`, `page_url`
- 发送到 `POST /api/extension/page-context`

`popup.js`：
- 读取 `chrome.storage.local` 中的 `page_context`
- 将用户输入问题与页面上下文提交到 `POST /api/extension/page-chat`
- 显示后端返回结果

### 5.2 FastAPI 端点

`/api/chat/query`：
- 负责多轮会话管理
- 调用意图解析、检索、UncertaintyDetector、ResponseGenerator
- 返回 `conversation_id` 便于后续跟踪

`/api/chat/webhook/{platform}`：
- 处理第三方平台 webhook 事件
- 依赖 `ChatManager.process_webhook_event()` 执行验证与消息解析

`/api/extension/page-context`：
- 接收扩展发送的页面商品上下文
- 返回确认和建议文本

`/api/extension/page-chat`：
- 基于页面上下文构造检索输入
- 调用生成器返回回答

`/api/knowledge/*`：
- 支持文档上传、任务查询、手动触发摄取、列表查询、健康检查
- 目前是知识库 RAG 入口

### 5.3 数据存储模块

- `storage_manager.py`：统一存储入口
- `redis_storage.py`：会话、消息历史持久化
- `postgres_storage.py`：摄取任务、商家信息、会话元数据持久化
- `MemorySessionStorage` / `MemoryIngestionStorage`：回退方案

## 6. 当前项目状态与建议修正

### 已实现的核心能力

- 浏览器扩展页面上下文采集
- FastAPI 本地服务与扩展 API
- 文档上传与后台摄取任务管理
- RAG 检索与 LLM 回答生成
- 意图解析与不确定性判定
- 多平台适配器架构框架
- Redis / PostgreSQL 可选持久化支持

### 当前仍需补齐的真实功能

- `TaobaoAdapter` / `JDAdapter` 的真实 API 集成实现
- 第三方平台 webhook 真实 payload 校验与解析
- 端到端商家隔离场景测试
- `storage_manager` 与实际 Redis/PostgreSQL 配置验证
- 浏览器扩展对不同页面版本的兼容性

### 重要说明

- 项目已经设计好“商家隔离 + 多商家目录 + 向量检索”结构
- RAG 部分通过知识摄取任务和向量库实现
- PostgreSQL 目前以任务元数据存储为主，若未配置会回退到内存
- 如果你打算“商家本地插件”，浏览器扩展 + 本地 FastAPI + Redis/本地文件存储是合理路径

## 7. 下一步建议

如果你希望，我可以继续：
- 生成一份“第三方平台 webhook 集成指南”
- 补全 `Taobao` / `JD` adapter stub 实现
- 添加“商家隔离 + 本地插件 + RAG”架构图
- 把 `README.md` 补成完整启动与配置说明
