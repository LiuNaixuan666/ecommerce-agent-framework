# 电商客服助手前端

这是一个基于React + TypeScript + Tailwind CSS构建的现代化前端界面，用于与电商客服AI助手进行交互。

## 功能特性

- 🗣️ **实时聊天**: 支持多轮对话，实时显示消息
- 📁 **会话管理**: 创建和管理多个对话会话
- 📤 **文件上传**: 上传文档到知识库进行学习
- 🎨 **现代化UI**: 基于Tailwind CSS的响应式设计
- 🔄 **API集成**: 通过代理与FastAPI后端通信

## 技术栈

- **React 18** - 用户界面框架
- **TypeScript** - 类型安全
- **Tailwind CSS** - 样式框架
- **Vite** - 构建工具和开发服务器
- **Lucide React** - 图标库

## 项目结构

```
frontend/
├── src/
│   ├── components/
│   │   └── ChatInterface.tsx    # 主聊天界面组件
│   ├── hooks/                   # React Hooks
│   ├── services/                # API服务
│   ├── App.tsx                  # 主应用组件
│   ├── main.tsx                 # 应用入口
│   └── index.css                # 全局样式
├── index.html                   # HTML模板
├── vite.config.js               # Vite配置
├── tailwind.config.js           # Tailwind配置
├── tsconfig.json                # TypeScript配置
└── package.json                 # 项目依赖
```

## 开发指南

### 安装依赖

```bash
cd frontend
npm install
```

### 启动开发服务器

```bash
npm run dev
```

服务器将在 `http://localhost:5173` 启动，并自动代理API请求到 `http://localhost:8000`。

### 构建生产版本

```bash
npm run build
```

### 预览生产构建

```bash
npm run preview
```

## API集成

前端通过Vite的代理配置与后端API通信：

- **聊天API**: `POST /api/chat/query` - 发送消息并获取回复
- **文件上传**: `POST /api/knowledge/upload` - 上传文档到知识库
- **触发摄取**: `POST /api/knowledge/ingest` - 处理上传的文档

## 组件说明

### ChatInterface

主聊天界面组件，包含以下功能：

- **会话管理**: 创建、切换和管理多个对话会话
- **消息显示**: 显示用户和AI的消息，支持时间戳
- **文件上传**: 拖拽或点击上传文档到知识库
- **实时交互**: 发送消息并实时显示AI回复
- **加载状态**: 显示发送消息时的加载动画

## 样式说明

项目使用Tailwind CSS进行样式管理：

- **颜色方案**: 蓝色主色调 (#3B82F6)，灰色辅助色
- **响应式设计**: 支持移动端和桌面端
- **暗色模式**: 可扩展支持暗色主题
- **动画效果**: 平滑的过渡和加载动画

## 浏览器支持

- Chrome 90+
- Firefox 88+
- Safari 14+
- Edge 90+

## 故障排除

### 常见问题

1. **端口冲突**: 如果5173端口被占用，可以在`vite.config.js`中修改端口
2. **API连接失败**: 确保后端服务器在8000端口运行
3. **样式不生效**: 确保Tailwind CSS正确配置并重启开发服务器

### 开发调试

- 使用浏览器开发者工具查看网络请求
- 检查控制台错误信息
- 验证API端点返回的数据格式