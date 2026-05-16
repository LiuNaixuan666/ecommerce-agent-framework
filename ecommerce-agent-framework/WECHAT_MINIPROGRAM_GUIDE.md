# 微信小程序智能客服 - 实施指南

## 🎯 项目目标
创建一个独立的AI客服小程序，为电商商家提供智能客服服务，无需依赖任何电商平台API权限。

## 📋 立即开始的步骤

### 1. 注册微信开发者账号 (今天完成)
```
访问：https://mp.weixin.qq.com/
注册账号 → 选择"小程序" → 完成实名认证
```

### 2. 下载开发工具 (今天完成)
```
下载微信开发者工具：https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html
安装并登录你的微信开发者账号
```

### 3. 创建小程序项目 (今天完成)
```
1. 打开微信开发者工具
2. 选择"创建小程序"
3. 填写项目信息：
   - 项目名称：AI智能客服
   - 项目目录：选择本地文件夹
   - AppID：使用测试AppID (mp...)
   - 开发模式：默认
   - 后端服务：不使用云服务
```

### 4. 基础页面搭建 (1-2天)

#### 页面结构
```
pages/
├── index/index     # 首页 - 商家选择
├── chat/chat       # 聊天页面
└── merchant/merchant # 商家详情页

app.js              # 小程序入口
app.json            # 全局配置
app.wxss            # 全局样式
```

#### 首页代码 (pages/index/index.wxml)
```xml
<view class="container">
  <view class="header">
    <text class="title">AI智能客服</text>
    <text class="subtitle">选择您要咨询的商家</text>
  </view>

  <view class="merchant-list">
    <view class="merchant-card" wx:for="{{merchants}}" wx:key="id" bindtap="onMerchantTap" data-id="{{item.id}}">
      <image class="logo" src="{{item.logo}}" mode="aspectFit"></image>
      <view class="info">
        <text class="name">{{item.name}}</text>
        <text class="desc">{{item.description}}</text>
      </view>
      <view class="rating">
        <text class="score">{{item.rating}}分</text>
      </view>
    </view>
  </view>
</view>
```

#### 首页样式 (pages/index/index.wxss)
```css
.container {
  padding: 20rpx;
  background-color: #f5f5f5;
  min-height: 100vh;
}

.header {
  text-align: center;
  margin-bottom: 40rpx;
}

.title {
  font-size: 48rpx;
  font-weight: bold;
  color: #333;
  display: block;
  margin-bottom: 16rpx;
}

.subtitle {
  font-size: 28rpx;
  color: #666;
}

.merchant-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
}

.merchant-card {
  background: white;
  border-radius: 16rpx;
  padding: 24rpx;
  display: flex;
  align-items: center;
  box-shadow: 0 2rpx 8rpx rgba(0,0,0,0.1);
}

.logo {
  width: 80rpx;
  height: 80rpx;
  border-radius: 8rpx;
  margin-right: 20rpx;
}

.info {
  flex: 1;
}

.name {
  font-size: 32rpx;
  font-weight: 600;
  color: #333;
  display: block;
  margin-bottom: 8rpx;
}

.desc {
  font-size: 26rpx;
  color: #666;
}

.rating {
  text-align: right;
}

.score {
  font-size: 24rpx;
  color: #ff6b35;
  font-weight: 600;
}
```

#### 首页逻辑 (pages/index/index.js)
```javascript
Page({
  data: {
    merchants: [
      {
        id: 'taobao_shop_001',
        name: 'XX旗舰店',
        description: '专业电子产品销售',
        logo: '/images/taobao.png',
        rating: '4.8'
      },
      {
        id: 'jd_shop_001',
        name: 'YY数码店',
        description: '京东自营数码产品',
        logo: '/images/jd.png',
        rating: '4.9'
      }
    ]
  },

  onMerchantTap: function(e) {
    const merchantId = e.currentTarget.dataset.id
    wx.navigateTo({
      url: `/pages/chat/chat?merchantId=${merchantId}`
    })
  }
})
```

### 5. 聊天页面开发 (2-3天)

#### 聊天页面结构
```
聊天页面需要：
- 消息列表显示
- 消息输入框
- 发送按钮
- 加载状态
- 错误处理
```

#### 聊天页面代码示例
```javascript
// pages/chat/chat.js
Page({
  data: {
    merchantId: '',
    merchantName: '',
    messages: [],
    inputValue: '',
    isLoading: false
  },

  onLoad: function(options) {
    this.setData({
      merchantId: options.merchantId,
      merchantName: options.merchantName || '商家客服'
    })

    // 加载历史消息
    this.loadChatHistory()
  },

  loadChatHistory: function() {
    // 从本地存储加载历史消息
    const history = wx.getStorageSync(`chat_${this.data.merchantId}`) || []
    this.setData({
      messages: history
    })
  },

  onInputChange: function(e) {
    this.setData({
      inputValue: e.detail.value
    })
  },

  sendMessage: function() {
    const content = this.data.inputValue.trim()
    if (!content) return

    // 添加用户消息
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: content,
      timestamp: new Date().toLocaleTimeString()
    }

    this.setData({
      messages: [...this.data.messages, userMessage],
      inputValue: '',
      isLoading: true
    })

    // 保存到本地存储
    this.saveMessages()

    // 调用AI接口
    this.callAIAPI(content)
  },

  callAIAPI: function(userMessage) {
    // 这里调用你的后端AI接口
    wx.request({
      url: 'http://localhost:8000/api/chat/query', // 替换为你的后端地址
      method: 'POST',
      data: {
        merchant_id: this.data.merchantId,
        user_query: userMessage,
        conversation_id: `wx_${this.data.merchantId}_${Date.now()}`
      },
      success: (res) => {
        if (res.data && res.data.response_text) {
          const aiMessage = {
            id: Date.now() + 1,
            type: 'ai',
            content: res.data.response_text,
            timestamp: new Date().toLocaleTimeString()
          }

          this.setData({
            messages: [...this.data.messages, aiMessage],
            isLoading: false
          })

          this.saveMessages()
        }
      },
      fail: (err) => {
        console.error('AI API call failed:', err)
        const errorMessage = {
          id: Date.now() + 1,
          type: 'system',
          content: '抱歉，网络连接失败，请稍后重试',
          timestamp: new Date().toLocaleTimeString()
        }

        this.setData({
          messages: [...this.data.messages, errorMessage],
          isLoading: false
        })
      }
    })
  },

  saveMessages: function() {
    wx.setStorageSync(`chat_${this.data.merchantId}`, this.data.messages)
  }
})
```

## 🔧 后端接口准备

### 1. 启动你的AI后端
```bash
cd ecommerce-agent-framework
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. 测试接口
```bash
curl -X POST http://localhost:8000/api/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "merchant_id": "taobao_shop_001",
    "user_query": "我的订单什么时候发货？",
    "conversation_id": "test_123"
  }'
```

## 🎨 界面效果预览

### 首页
```
┌─────────────────────────────────┐
│        AI智能客服                │
│     选择您要咨询的商家           │
│                                 │
│ ┌─────────────────────────────┐ │
│ │ [Logo] XX旗舰店             │ │
│ │ 专业电子产品销售            │ │
│ │                    4.8分    │ │
│ └─────────────────────────────┘ │
│                                 │
│ ┌─────────────────────────────┐ │
│ │ [Logo] YY数码店             │ │
│ │ 京东自营数码产品            │ │
│ │                    4.9分    │ │
│ └─────────────────────────────┘ │
└─────────────────────────────────┘
```

### 聊天页面
```
┌─────────────────────────────────┐
│ XX旗舰店                        │
├─────────────────────────────────┤
│ 您好！请问有什么可以帮您的？     │ ← AI回复
├─────────────────────────────────┤
│ 我的订单什么时候发货？          │ ← 用户消息
├─────────────────────────────────┤
│ [输入框]                        │
│ [发送按钮]                      │
└─────────────────────────────────┘
```

## 🚀 下一步计划

### Phase 1：基础功能 (本周完成)
- [x] 小程序框架搭建
- [ ] 商家选择页面
- [ ] 基础聊天界面
- [ ] 后端API对接

### Phase 2：核心功能 (下周)
- [ ] 知识库上传系统
- [ ] 商家管理后台
- [ ] 用户评价系统
- [ ] 对话历史持久化

### Phase 3：高级功能 (第三周)
- [ ] 语音消息支持
- [ ] 图片识别咨询
- [ ] 智能问题推荐
- [ ] 数据统计分析

## 💡 关键提醒

1. **测试AppID**：初期可以使用微信提供的测试AppID开发
2. **域名配置**：小程序需要配置合法域名才能调用后端API
3. **HTTPS要求**：生产环境必须使用HTTPS
4. **审核准备**：开发完成后需要提交微信审核

## 🎯 今天就开始行动！

1. **立即注册微信开发者账号**
2. **下载微信开发者工具**
3. **创建你的第一个小程序页面**

有任何问题随时问我，我会一步步指导你完成这个项目！🚀