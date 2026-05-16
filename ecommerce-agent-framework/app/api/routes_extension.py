from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

from app.agent.response_generator import ResponseGenerator

router = APIRouter(prefix="/api/extension", tags=["extension"])
response_generator = ResponseGenerator()


class PageContextRequest(BaseModel):
    merchant_id: Optional[str] = "default"
    page_url: str
    product_name: Optional[str] = None
    sku: Optional[str] = None
    price: Optional[str] = None
    stock: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    user_query: Optional[str] = None


class PageChatRequest(BaseModel):
    merchant_id: Optional[str] = "default"
    conversation_id: Optional[str] = None
    page_context: PageContextRequest
    user_query: str


@router.post("/page-context")
async def page_context(request: PageContextRequest) -> Dict[str, Any]:
    """接收浏览器扩展发送的页面上下文信息。"""
    received_at = datetime.now().isoformat()
    product_info = {
        "product_name": request.product_name,
        "sku": request.sku,
        "price": request.price,
        "stock": request.stock,
        "page_url": request.page_url,
        "extra": request.extra,
    }

    recommendation = "请继续输入用户问题，或者直接在页面中选择需要回答的内容。"
    if request.stock and request.stock.lower() in ["0", "out of stock", "无货", "缺货"]:
        recommendation = "当前页面显示库存不足，建议询问用户是否愿意等待补货或推荐替代商品。"

    return {
        "status": "received",
        "received_at": received_at,
        "merchant_id": request.merchant_id,
        "product_info": product_info,
        "recommendation": recommendation,
    }


@router.post("/page-chat")
async def page_chat(request: PageChatRequest) -> Dict[str, Any]:
    """使用页面上下文和用户问题生成智能回答。"""
    page = request.page_context
    structured_data = {
        "product_name": page.product_name,
        "sku": page.sku,
        "price": page.price,
        "stock": page.stock,
    }
    context_text = "\n".join(
        [f"{k}: {v}" for k, v in structured_data.items() if v is not None]
    )
    retrieval_results = {
        "documents": [
            {
                "content": f"浏览器页面上下文：{context_text}",
                "metadata": {"source": "browser_extension"},
                "source": "browser_extension"
            }
        ],
        "scores": [1.0],
        "structured_data": structured_data,
        "retrieval_type": "extension_page"
    }

    answer = await response_generator.generate_grounded_response(
        user_query=request.user_query,
        retrieval_results=retrieval_results,
        merchant_id=request.merchant_id,
    )

    return {
        "status": "ok",
        "merchant_id": request.merchant_id,
        "conversation_id": request.conversation_id,
        "page_context": page.dict(),
        "user_query": request.user_query,
        "answer": answer,
        "source": "extension_poc",
    }
