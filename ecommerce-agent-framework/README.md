# E-commerce Agent Framework

智能电商客服系统，支持多平台集成、RAG检索增强和不确定性检测。

## 🚀 快速开始

### 1. 环境配置

```bash
# 复制环境配置文件
cp .env.example .env

# 编辑 .env 文件，填入你的 API keys 和平台配置
nano .env
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动服务

```bash
# 开发模式
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 生产模式
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 📱 平台适配器配置

### 支持的平台

- ✅ **小红书 (Xiaohongshu)** - 已实现基础适配器
- 🚧 **淘宝 (Taobao)** - 计划中
- 🚧 **京东 (JD)** - 计划中
- 🚧 **拼多多 (PDD)** - 计划中

### 小红书配置

1. 注册小红书开发者账号
2. 创建应用获取 AppID 和 AppSecret
3. 配置 Webhook 接收消息
4. 在 `.env` 中设置：

```env
XIAOHONGSHU_APP_ID=your_app_id
XIAOHONGSHU_APP_SECRET=your_app_secret
XIAOHONGSHU_WEBHOOK_TOKEN=your_webhook_token
XIAOHONGSHU_MERCHANT_ID=your_merchant_id
```

### 消息处理流程

1. **接收消息**: 通过 Webhook 或轮询接收平台消息
2. **对话管理**: 创建/更新对话记录，保持上下文
3. **AI回复**: 调用本地AI引擎生成智能回复
4. **发送回复**: 通过平台API发送回复给用户

## 🛠️ 核心组件

### 对话管理器 (ChatManager)
- 多平台对话协调
- 并发处理控制
- 消息队列管理

### 平台适配器 (ChatAdapter)
- 统一的平台接口
- 消息收发抽象
- 平台特定功能

### AI引擎 (Engine)
- 意图解析
- 知识检索
- 回复生成

## 📊 API 接口

### 聊天接口
- `POST /api/chat/query` - 发送聊天消息

### 知识库接口
- `POST /api/knowledge/upload` - 上传知识文档
- `POST /api/knowledge/ingest` - 触发文档摄取
- `GET /api/knowledge/list-uploads` - 获取上传任务列表

## 🔧 开发指南

### 添加新平台适配器

1. 实现 `ChatAdapter` 接口：

```python
from app.connectors.chat_base import ChatAdapter

class YourPlatformAdapter(ChatAdapter):
    @property
    def platform_name(self) -> str:
        return 'your_platform'

    async def initialize(self, config: Dict[str, Any]) -> bool:
        # 初始化逻辑
        pass

    async def send_message(self, conversation_id: str, content: str) -> bool:
        # 发送消息逻辑
        pass

    # 实现其他必要方法...
```

2. 在 `ChatManager` 中注册适配器
3. 在配置中添加平台设置

### 扩展AI能力

- 修改 `app/agent/` 中的组件
- 调整 `app/config.py` 中的参数
- 添加新的意图识别或回复生成逻辑

## 📈 监控和日志

- 实时查看平台连接状态
- 消息处理统计
- 错误日志记录
- 性能指标监控

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支
3. 提交变更
4. 发起 Pull Request

## 📄 许可证

MIT License