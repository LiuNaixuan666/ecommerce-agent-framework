# 微信公众号AI客服 - 快速实施指南

## 🎯 目标
**5天内上线** - 创建一个用户只需点击"联系客服"就能获得AI智能回复的系统。

## 📋 立即执行步骤

### Day 1：基础搭建（今天完成）

#### 1. 注册微信公众号
```
1. 访问：https://mp.weixin.qq.com/
2. 选择"订阅号"（免费）或"服务号"（¥300/年，推荐）
3. 填写基本信息：
   - 账号名称：AI智能客服
   - 账号类型：服务号
   - 主体类型：个人/企业
4. 完成实名认证
```

#### 2. 准备服务器环境
```bash
# 确保你的FastAPI后端支持HTTPS
# 如果没有域名，可以先用测试号开发

# 安装微信SDK
pip install wechatpy

# 创建公众号接口文件
touch app/api/wechat_official.py
```

#### 3. 公众号配置
```
公众号后台 → 开发 → 基本配置
- AppID: wx1234567890
- AppSecret: abcdef123456
- 服务器地址: https://yourdomain.com/api/wechat/callback
- 令牌(Token): your_token_123
- 消息加解密密钥: your_encoding_aes_key
```

### Day 2：核心接口开发（明天完成）

#### 微信消息处理接口
```python
# app/api/wechat_official.py
from fastapi import APIRouter, Request, HTTPException
from wechatpy import parse_message, create_reply
from wechatpy.utils import check_signature
from app.engine import AIEngine
import logging

router = APIRouter()
ai_engine = AIEngine()
logger = logging.getLogger(__name__)

# 公众号配置（从环境变量读取）
WECHAT_TOKEN = "your_token_here"
WECHAT_AES_KEY = "your_aes_key_here"
WECHAT_APP_ID = "your_app_id_here"

@router.get("/wechat/callback")
async def wechat_verify(
    signature: str,
    timestamp: str,
    nonce: str,
    echostr: str
):
    """微信服务器验证"""
    try:
        check_signature(WECHAT_TOKEN, signature, timestamp, nonce)
        return echostr
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/wechat/callback")
async def wechat_callback(request: Request):
    """处理微信消息"""
    try:
        # 获取原始数据
        body = await request.body()
        signature = request.query_params.get("signature")
        timestamp = request.query_params.get("timestamp")
        nonce = request.query_params.get("nonce")

        # 验证签名
        check_signature(WECHAT_TOKEN, signature, timestamp, nonce)

        # 解析消息
        msg = parse_message(body)

        logger.info(f"Received message: {msg.type} from {msg.source}")

        # 处理不同类型的消息
        if msg.type == "text":
            response = await handle_text_message(msg)
        elif msg.type == "voice":
            response = await handle_voice_message(msg)
        elif msg.type == "image":
            response = await handle_image_message(msg)
        else:
            response = create_reply("抱歉，我暂时只能处理文字消息", msg)

        # 返回XML格式回复
        return response.render()

    except Exception as e:
        logger.error(f"Message processing failed: {e}")
        return create_reply("系统繁忙，请稍后重试", msg).render()

async def handle_text_message(msg):
    """处理文字消息"""
    user_query = msg.content.strip()

    # 简单商家识别（可以通过消息内容或用户参数识别）
    merchant_id = extract_merchant_from_message(user_query)

    if not merchant_id:
        # 默认商家或让用户选择
        return create_reply(
            "您好！我是AI智能客服，请告诉我您要咨询哪个商家的产品？\n\n" +
            "例如：\n" +
            "• XX旗舰店的订单问题\n" +
            "• YY商城的退货流程",
            msg
        )

    try:
        # 调用AI引擎
        ai_response = await ai_engine.generate_response(
            merchant_id=merchant_id,
            user_query=user_query,
            conversation_id=f"wx_{msg.source}",
            platform="wechat_official"
        )

        # 创建回复
        reply = create_reply(ai_response["response_text"], msg)

        # 如果有快捷按钮，添加按钮
        if ai_response.get("quick_replies"):
            # 公众号支持自定义菜单，这里可以添加快捷回复
            pass

        return reply

    except Exception as e:
        logger.error(f"AI response failed: {e}")
        return create_reply("抱歉，AI服务暂时不可用，请稍后重试", msg)

def extract_merchant_from_message(message: str) -> str:
    """从消息中提取商家信息"""
    # 简单关键词匹配
    merchant_keywords = {
        "taobao_001": ["淘宝", "天猫", "XX旗舰店"],
        "jd_001": ["京东", "YY商城"],
        "pdd_001": ["拼多多", "ZZ店铺"]
    }

    for merchant_id, keywords in merchant_keywords.items():
        if any(keyword in message for keyword in keywords):
            return merchant_id

    return None

async def handle_voice_message(msg):
    """处理语音消息"""
    # 将语音转换为文字（需要额外服务）
    return create_reply("语音消息已收到，我正在处理中...", msg)

async def handle_image_message(msg):
    """处理图片消息"""
    return create_reply("图片已收到，我来帮您分析一下商品问题", msg)
```

#### 消息路由配置
```python
# app/main.py
from app.api.wechat_official import router as wechat_router

app = FastAPI()
app.include_router(wechat_router, prefix="/api", tags=["wechat"])
```

### Day 3：AI引擎集成（后天完成）

#### 对话管理增强
```python
# app/chat/wechat_manager.py
from typing import Dict, Optional
from app.engine import AIEngine
from app.storage import ConversationStorage

class WechatConversationManager:
    def __init__(self):
        self.ai_engine = AIEngine()
        self.storage = ConversationStorage()
        self.active_conversations: Dict[str, dict] = {}

    async def handle_message(
        self,
        openid: str,
        message: str,
        merchant_id: Optional[str] = None
    ) -> dict:
        """处理微信消息"""
        # 获取对话历史
        conversation = await self.storage.get_conversation(
            conversation_id=f"wx_{openid}",
            platform="wechat_official"
        )

        if not conversation:
            conversation = {
                "id": f"wx_{openid}",
                "merchant_id": merchant_id,
                "platform": "wechat_official",
                "messages": [],
                "created_at": datetime.now()
            }

        # 添加用户消息
        conversation["messages"].append({
            "role": "user",
            "content": message,
            "timestamp": datetime.now()
        })

        # 生成AI回复
        response = await self.ai_engine.generate_response(
            merchant_id=merchant_id,
            user_query=message,
            conversation_history=conversation["messages"],
            platform="wechat_official"
        )

        # 添加AI回复
        conversation["messages"].append({
            "role": "assistant",
            "content": response["response_text"],
            "timestamp": datetime.now()
        })

        # 保存对话
        await self.storage.save_conversation(conversation)

        return response
```

### Day 4：测试与调试（大后天完成）

#### 1. 本地测试
```python
# tests/test_wechat_official.py
import pytest
from app.api.wechat_official import handle_text_message
from wechatpy.messages import TextMessage

def test_text_message_handling():
    """测试文字消息处理"""
    # 创建模拟消息
    msg = TextMessage({
        "ToUserName": "gh_test",
        "FromUserName": "test_user",
        "CreateTime": "1234567890",
        "MsgType": "text",
        "Content": "我的订单什么时候发货？",
        "MsgId": "123456789"
    })

    # 处理消息
    response = await handle_text_message(msg)

    # 验证回复
    assert response is not None
    assert "发货" in response.content or "订单" in response.content
```

#### 2. 公众号测试号
```
1. 访问：https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login
2. 获取测试AppID和AppSecret
3. 配置测试回调URL
4. 用微信扫码测试
```

### Day 5：商家接入与上线（第五天完成）

#### 商家绑定接口
```python
# app/api/merchant_wechat.py
@router.post("/merchant/bind_wechat")
async def bind_wechat_account(
    merchant_id: str,
    wechat_app_id: str,
    wechat_app_secret: str,
    current_user = Depends(get_current_merchant)
):
    """商家绑定微信公众号"""
    # 验证公众号信息
    # 保存绑定关系
    # 配置回调URL

    return {"success": True, "message": "公众号绑定成功"}
```

#### 上线检查清单
- [ ] 公众号认证完成
- [ ] 服务器HTTPS配置
- [ ] 回调URL配置正确
- [ ] AI引擎集成测试
- [ ] 消息处理测试
- [ ] 错误处理测试
- [ ] 商家知识库上传

## 🎯 用户体验验证

### 测试场景
```
1. 新用户咨询："我想问一下XX旗舰店的订单问题"
2. AI回复："您好！我是XX旗舰店的智能客服，请告诉我您的订单号"
3. 用户回复："订单号是123456789"
4. AI回复："查询到您的订单状态：已发货，预计明天送达"
```

### 性能指标
- **响应时间**：< 3秒
- **成功率**：> 95%
- **用户满意度**：> 4.5星

## 🚀 立即开始

### 今天行动
1. **注册微信公众号**（30分钟）
2. **配置服务器环境**（1小时）
3. **创建基础接口代码**（2小时）

### 技术栈
- **后端**：FastAPI + wechatpy
- **AI引擎**：现有RAG系统
- **数据库**：现有存储系统
- **部署**：Docker + 云服务器

## 💡 关键提醒

1. **HTTPS必须** - 微信要求回调URL必须是HTTPS
2. **域名备案** - 如果用国内服务器，需要ICP备案
3. **测试号优先** - 先用测试号开发，功能稳定后再切换正式号
4. **消息加密** - 生产环境必须开启消息加密

这个方案真正实现了**一键直达，秒级响应**的用户体验！用户在电商平台点击"联系客服"就能立即获得AI智能服务。

**准备开始了吗？我可以帮你编写具体的代码，或者解决开发过程中的任何问题！** 🚀