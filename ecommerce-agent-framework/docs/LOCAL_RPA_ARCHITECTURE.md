# 本地 RPA 电商智能客服架构设计

## 1. 架构目标

本架构目标是支持商家在本地运行统一的电商客服 Agent，通过自研 Local Agent / RPA Runtime 与多个电商平台网页版客服系统协作，在不依赖平台开放 API 的情况下完成消息读取、AI 自动回复、自动发送、发送结果回写和异常转人工。

当前实现主线为自研 Local Agent。影刀等第三方 RPA 工具仅作为可选验证工具，不作为核心执行层。

架构需要满足：

- 本地运行
- 多平台输入标准化
- 商家数据库可插拔
- 商品和政策知识库可绑定上下文
- 回复可审计
- 支持后续从 RPA 升级到平台 API 或 ERP 对接

## 2. 总体架构

系统可以拆分为七层：

1. RPA 接入层
2. 会话标准化层
3. Agent 编排层
4. 知识检索层
5. 商家数据适配层
6. 记忆与模板层
7. 前端工作台

简化数据流：

```text
电商平台网页版客服
        |
        v
自研 Local Agent / 可选第三方 RPA
        |
        v
本地 RPA HTTP API
        |
        v
会话标准化层
        |
        v
Agent 编排层
   |        |        |
   v        v        v
知识库   商家数据库   会话记忆/模板
   |        |        |
   ---------+---------
            |
            v
       回复生成与风控
            |
            v
推荐回复返回 RPA / 前端工作台
            |
            v
低风险自动发送 / 高风险转人工
```

## 3. 核心模块

### 3.1 RPA 接入层

RPA 接入层负责接收来自影刀 RPA、浏览器插件或其他自动化工具的消息。

建议提供以下接口：

```text
POST /api/rpa/inbound-message
POST /api/rpa/recommend-reply
POST /api/rpa/confirm-sent
POST /api/rpa/session-context
```

`inbound-message` 请求示例：

```json
{
  "platform": "pinduoduo",
  "shop_id": "local_shop_001",
  "session_id": "pdd_session_123",
  "buyer_message": "这本书适合13岁孩子看吗？",
  "product_id": "BOOK_001",
  "sku": "BOOK_001_STANDARD",
  "product_title": "少年科普阅读套装",
  "order_id": null,
  "page_context": {
    "url": "https://example.com/chat",
    "raw_title": "少年科普阅读套装"
  }
}
```

标准回复示例：

```json
{
  "recommended_reply": "这套书比较适合13岁左右的孩子阅读，内容偏科普启蒙和兴趣拓展。如果孩子平时阅读量适中，可以直接选择标准套装。",
  "risk_level": "low",
  "auto_send_allowed": true,
  "requires_human_review": false,
  "handoff_reason": null,
  "missing_info": [],
  "sources": [
    {
      "type": "product_doc",
      "title": "少年科普阅读套装商品说明",
      "product_id": "BOOK_001"
    }
  ],
  "confidence": 0.86
}
```

### 3.2 会话标准化层

不同平台的消息结构不同，系统内部必须统一为标准模型。

标准会话输入字段：

- platform
- shop_id
- session_id
- buyer_message
- product_id
- sku
- product_title
- order_id
- buyer_id，可选
- page_context
- recent_messages

标准化层负责：

- 补全缺失字段
- 识别平台
- 合并 RPA 页面上下文
- 查找当前会话历史
- 生成 Agent 可用的上下文包
- 保证同一 session_id 内消息按顺序进入处理队列
- 保证不同 session_id 的消息可以并发处理

### 3.3 Agent 编排层

Agent 编排层负责决定如何回答。

建议流程：

1. 读取标准化输入。
2. 识别意图。
3. 判断是否高风险。
4. 检索短期上下文和会话摘要。
5. 查询商品数据库。
6. 检索商品级知识库。
7. 检索平台政策和店铺政策。
8. 检索问答模板。
9. 必要时调用外部搜索。
10. 生成结构化回复。
11. 保存问答记录。

意图类型建议包括：

- product_consultation
- price_consultation
- inventory_consultation
- shipping_policy
- return_policy
- order_status
- recommendation
- complaint
- refund_dispute
- unclear
- out_of_scope

### 3.4 知识检索层

知识检索层负责 RAG。

知识需要按范围分层：

- global：全店通用
- platform：平台特定
- product：商品特定
- sku：SKU 特定
- template：问答模板

chunk metadata 建议：

```json
{
  "merchant_id": "local",
  "platform": "pinduoduo",
  "scope": "product",
  "product_id": "BOOK_001",
  "sku": "BOOK_001_STANDARD",
  "doc_type": "product_manual",
  "policy_scope": null,
  "source_file": "BOOK_001_manual.md",
  "chunk_id": "chunk_001"
}
```

检索优先级：

1. 当前 product_id / sku 绑定知识
2. 当前 platform 绑定政策
3. 全店政策
4. 问答模板
5. 非绑定但可能相关的商品知识

### 3.5 商家数据适配层

商家数据适配层负责接入不同商家的数据库。

系统内部不直接依赖商家原始字段，而使用标准商品模型：

```json
{
  "product_id": "BOOK_001",
  "sku": "BOOK_001_STANDARD",
  "title": "少年科普阅读套装",
  "category": "图书",
  "price": 99.0,
  "stock": 32,
  "status": "on_sale",
  "description": "适合青少年阅读的科普图书套装",
  "updated_at": "2026-06-12T10:00:00"
}
```

每个数据源配置应包含：

- source_id
- source_type
- connection_config
- table_config
- field_mapping
- enabled

字段映射示例：

```json
{
  "product_id": "item_id",
  "sku": "sku_code",
  "title": "product_name",
  "price": "sale_price",
  "stock": "available_qty",
  "description": "intro"
}
```

适配器接口建议：

```text
get_product(product_id)
get_product_by_sku(sku)
search_products(query)
get_inventory(sku)
get_price(sku)
get_order(order_id)
```

### 3.6 记忆与模板层

记忆分为：

- conversation_messages：原始会话消息
- conversation_summaries：会话摘要
- qa_templates：商家确认后的问答模板
- unresolved_questions：AI 不会答或转人工的问题

上下文策略：

1. 最近 4-8 轮消息直接进入上下文。
2. 超过阈值后生成会话摘要。
3. 长期历史通过 product_id、buyer_id、session_id、问题语义检索。
4. 高风险问题不因为历史相似就自动承诺。

### 3.7 回复生成与风控层

最终输出不应只是文本，而是结构化结果。

标准输出字段：

- recommended_reply
- risk_level
- auto_send_allowed
- requires_human_review
- handoff_reason
- missing_info
- sources
- confidence
- debug_trace，可选

风险等级：

- low：可直接推荐
- medium：建议人工检查
- high：必须转人工

自动发送策略：

- low 风险且高置信度：允许 RPA 自动发送
- medium 风险：默认不自动发送，可由商家配置是否允许
- high 风险：禁止自动发送，必须转人工
- 缺少关键信息：禁止自动发送，先追问或转人工

必须转人工的场景：

- 投诉
- 退款纠纷
- 差评威胁
- 平台处罚
- 法律风险
- 赔偿承诺
- 超出政策承诺
- 数据缺失但用户要求确定答案

## 3.9 多平台多会话并发架构

系统需要支持多个 RPA 机器人同时接入，例如拼多多、淘宝、京东同时有买家咨询。

建议采用“平台入口并发、会话内部串行”的模型：

```text
PDD RPA ----\
Taobao RPA --+--> RPA API --> Message Queue --> Session Worker --> Agent
JD RPA -----/
```

处理规则：

- 每条消息必须包含 platform、shop_id、session_id。
- 不同 session_id 可以并行处理。
- 同一 session_id 必须按消息时间顺序处理。
- 同一 session_id 正在生成回复时，新消息进入该会话队列。
- 如果同一买家连续发送多条短消息，可以先合并再生成回复。
- 自动发送前再次检查该 session 是否已有更新消息，避免回复过期上下文。

推荐状态：

- pending：已收到，等待处理
- processing：正在生成回复
- auto_sent：已自动发送
- handoff_required：需要人工
- failed：处理失败
- skipped_stale：因上下文过期跳过

### 3.8 前端工作台

前端需要承载四类页面：

1. 客服工作台
2. 知识库管理
3. 数据源配置
4. 问答模板与历史会话

客服工作台建议布局：

- 左侧：会话列表
- 中间：买家消息和 AI 推荐回复
- 右侧：商品信息、库存、政策命中、引用来源、风险提示

## 4. 本地数据存储建议

MVP 可以使用：

- SQLite：本地配置、会话、模板、模拟商家数据库
- Chroma：向量库
- 文件系统：原始上传文档

后续可选：

- PostgreSQL：更强的结构化数据和多用户能力
- Redis：任务队列和缓存

## 5. 数据库建议表

### 5.1 datasource_configs

保存商家数据源连接配置和字段映射。

### 5.2 normalized_products

保存同步后的标准商品数据，减少每次实时访问商家数据库的成本。

### 5.3 conversations

保存客服会话。

### 5.4 conversation_messages

保存每条买家和客服消息。

### 5.5 conversation_summaries

保存长会话摘要。

### 5.6 qa_templates

保存商家确认后的问答模板。

### 5.7 unresolved_questions

保存 AI 未解决、转人工、低置信度问题。

### 5.8 rpa_events

保存 RPA 消息读取、回复回填、发送确认等事件。

## 6. 可插拔设计

系统需要在以下层面保持可插拔：

- RPA 工具可替换
- 大模型提供商可替换
- Embedding 模型可替换
- 向量数据库可替换
- 商家数据库可替换
- 外部搜索提供商可替换

建议抽象接口：

```text
RpaMessageAdapter
MerchantDataAdapter
KnowledgeRetriever
LLMClient
EmbeddingClient
ExternalSearchProvider
RiskEvaluator
MemoryStore
```

## 7. 与平台 API 的关系

RPA 是当前 MVP 入口，但架构不应把自己锁死在 RPA。

未来如果拿到平台 API 权限，平台 API adapter 可以直接复用：

- 会话标准化层
- Agent 编排层
- 商家数据库适配层
- 知识库
- 记忆与模板
- 风控

因此 RPA 和平台 API 都应被看成“消息入口适配器”。

## 8. 当前系统演进方向

当前项目已有：

- FastAPI 后端
- 基础 chat 接口
- 基础知识库上传
- Chroma 向量库
- 意图识别
- 浏览器插件雏形
- 多 merchant 目录结构
- 部分 platform adapter 骨架

下一步建议优先演进：

1. 新增 RPA 标准接口。
2. 改造 chat 输出为结构化客服回复。
3. 增加本地商家数据库模拟和字段映射。
4. 上传文档时增加 scope、platform、product_id、sku metadata。
5. 前端从聊天 demo 改为客服工作台。
6. 增加多平台多会话队列，支持低风险自动发送和异常转人工。
