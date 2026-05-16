# 平台接入与多平台实时回复架构

## 1. 平台接入方法评估

### 1.1 直接平台 API 集成
- 优点：实时、稳定、可获取历史会话和用户信息
- 缺点：需要平台权限、审批、SDK/接口差异大

### 1.2 浏览器扩展 + 本地代理（PoC）
- 优点：快速验证、无需平台开放 API、可直接读取页面 DOM 和动态商品信息
- 缺点：只能用于浏览器端、需用户安装扩展、对平台前端结构依赖较高

### 1.3 本地化插件 / 代理层
- 优点：降低服务器压力、数据本地化、私密性好
- 缺点：部署成本和维护成本高，需要用户环境支持

### 1.4 结论
本项目当前优先级建议：
1. 先做浏览器扩展 PoC，验证“从页面读取商品动态数据 + 发送到本地 FastAPI 生成回答”的可行性。
2. 作为后续，可继续推进“本地部署代理 / Windows 服务”、“浏览器插件 + 本地服务”组合。
3. 如果有平台 API 访问权限，再逐步切换到标准适配器模式。

## 2. 浏览器扩展 PoC 的定位

### 2.1 核心思路
- content script 负责从商品页面提取：商品名、价格、库存、SKU、URL、促销信息等
- local extension 将这些信息发送到本地 FastAPI
- 后端基于页面上下文生成回答或补充建议

### 2.2 为什么页面读取很合理
- 商品库存/价格通常不会通过平台开放 API 直接暴露给第三方
- 浏览器端页面实际上已经显示这些动态信息，所以扩展直接读取更可行
- 这是一种“前端即数据源”的轻量接入方案

### 2.3 适用场景
- 商家员工在平台后台自己使用本系统给买家答疑
- 需要快速验证对话助手能力，不依赖平台审批
- 平台具有复杂前端结构但可以通过 DOM 提取关键字段

## 3. 多平台实时回复架构设计

### 3.1 统一接口层
1. `ChatAdapter`：定义通用协议
   - `initialize(config)`
   - `listen_for_messages()`
   - `send_message(conversation_id, content)`
   - `get_conversation_history(conversation_id)`
   - `close()`

2. `ChatAdapterFactory`：注册 / 创建不同平台适配器
   - 允许 `platform` 与 `adapter_class_path` 两种配置方式
   - 使适配器实现可插拔、动态加载

### 3.2 ChatManager 设计
- 负责：
  - 监听多个平台消息源
  - 统一入队、调度、AI 生成回复
  - 维护会话状态、历史和多平台映射
- 当前实现已支持：
  - `platform_configs` 配置多平台
  - `listen_for_messages()` 轮询或 webhook
  - `send_message()` 统一发送
  - `message_queue` 异步处理

### 3.3 实时响应路径
1. 平台消息进入 adapter
2. adapter 生成 `ChatMessage` 并进入 `ChatManager` 队列
3. `ChatManager` 调用 `engine` / `chat_query` 生成回答
4. 回答通过平台 adapter 发送回用户
5. 会话历史同步存储，支持后续多轮

### 3.4 关键扩展点
- **多平台消息一致性**：通过 `Conversation.platform` 与 `metadata.platform` 保存来源
- **防抖与去重**：同一会话内重复澄清或重复消息需要限流
- **动态上下文注入**：浏览器扩展可把页面 DOM 数据作为结构化上下文传入后端
- **本地部署**：Docker + Windows 服务支持边缘部署，降低平台数据泄露风险

## 4. 当前实现补充说明

### 4.1 已完成的支持
- `ChatManager.initialize()` 现在支持从配置读取 adapter 类并动态加载
- 已注册 `xiaohongshu` 适配器为示例
- 通过 `app/api/routes_extension.py` 实现浏览器扩展 PoC 后端接口
- 提供 Dockerfile 和 Windows 服务安装脚本

### 4.2 下一步建议
- 为每个平台补充专用 `ChatAdapter`，包含真实 webhook/SDK
- 在 `ChatAdapterFactory` 中注册更多 adapter 类型（`taobao`, `jd`, `pdd`）
- 为浏览器扩展增加平台规则提取器，支持淘宝、京东等页面结构
- 使用 Redis 或 PostgreSQL 存储会话状态，提升多平台扩展稳定性
