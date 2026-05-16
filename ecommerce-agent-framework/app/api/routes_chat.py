# routes_chat.py
"""
聊天 API 路由：整合意图解析、知识检索、不确定性检测、LLM 生成的完整工作流

对应论文中的工作流编排：
  Query → Intent Parser → Retriever → Uncertainty Detector → LLM Generator → Response
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict
import logging
import os
import re
import hashlib
import math
import uuid
from datetime import datetime
from datetime import timedelta

from app.agent.intent_parser import IntentParser
from app.agent.uncertainty_detector import UncertaintyDetector
from app.agent.response_generator import ResponseGenerator
from app.connectors import mock_adapter
from app.engine import engine
from app.rag.retriever import Retriever
from app.rag.reranker import Reranker
from app.config import settings
from app.models.schemas import ConversationMessage, ConversationHistoryRequest, ConversationHistoryResponse
from app.storage.storage_manager import storage_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


# ==================== 会话管理 ====================

def _create_conversation_id() -> str:
    """创建新的会话 ID"""
    return str(uuid.uuid4())


def _get_or_create_conversation(conversation_id: Optional[str] = None, merchant_id: Optional[str] = None) -> str:
    """获取或创建会话"""
    if conversation_id:
        # 检查会话是否存在
        existing = storage_manager.get_conversation(conversation_id)
        if existing:
            return conversation_id

    # 创建新会话
    new_id = _create_conversation_id()
    conversation_data = {
        "conversation_id": new_id,
        "merchant_id": merchant_id,
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
        "last_intent": None,
        "status": "active",
        "message_count": 0
    }

    # 保存到存储
    storage_manager.save_conversation(new_id, conversation_data)
    storage_manager.save_conversation_metadata(conversation_data)

    return new_id


def _add_message_to_conversation(conversation_id: str, role: str, content: str) -> None:
    """添加消息到会话"""
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    }

    # 添加到消息历史
    storage_manager.add_message(conversation_id, message)

    # 更新会话元数据
    conversation_data = storage_manager.get_conversation(conversation_id)
    if conversation_data:
        conversation_data["last_updated"] = datetime.now().isoformat()
        conversation_data["message_count"] = conversation_data.get("message_count", 0) + 1
        storage_manager.save_conversation(conversation_id, conversation_data)
        storage_manager.update_conversation_metadata(conversation_id, {
            "last_updated": conversation_data["last_updated"],
            "message_count": conversation_data["message_count"]
        })


def _get_conversation_history(conversation_id: str, limit: int = 10, offset: int = 0) -> List[Dict]:
    """获取会话历史"""
    return storage_manager.get_messages(conversation_id, limit, offset)


class LocalTextEmbeddings:
    """本地词向量降级实现，用于在无 OpenAI API 时保持向量检索能力。"""

    def __init__(self, dimension: int = 512):
        self.dimension = dimension

    def _embed_text(self, text: str):
        tokens = re.findall(r"\w+", text.lower())
        vector = [0.0] * self.dimension
        for token in tokens:
            index = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16) % self.dimension
            vector[index] += 1.0

        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def embed_documents(self, texts):
        return [self._embed_text(text) for text in texts]

    def embed_query(self, text):
        return self._embed_text(text)


# 创建全局实例（在生产环境中应该使用依赖注入）
try:
    intent_parser = IntentParser()
    logger.info("Initialized IntentParser with configured LLM provider")
except Exception as e:
    logger.warning(f"Failed to initialize IntentParser with configured LLM: {e}. Falling back to keyword-based parser.")

    class FallbackIntentParser:
        """基于关键词的意图解析（降级方案）"""

        def parse(self, user_query: str):
            from app.agent.intent_parser import IntentSchema

            query_lower = user_query.lower()

            if any(word in user_query for word in ['价格', '多少钱', '价位', '售价']):
                intent = 'PRODUCT_INQUIRY'
            elif any(word in user_query for word in ['退货', '退款', '退换', '政策', '规则', '运费', '邮费']):
                intent = 'POLICY_INQUIRY'
            elif any(word in user_query for word in ['订单', '物流', '发货', '快递', '状态', '追踪']):
                intent = 'ORDER_SERVICE'
            elif any(word in query_lower for word in ['price', 'cost', 'how much', 'expensive']):
                intent = 'PRODUCT_INQUIRY'
            elif any(word in query_lower for word in ['return', 'refund', 'policy', 'shipping', 'fee']):
                intent = 'POLICY_INQUIRY'
            elif any(word in query_lower for word in ['order', 'status', 'tracking', 'delivery']):
                intent = 'ORDER_SERVICE'
            else:
                intent = 'CHITCHAT'

            return IntentSchema(
                intent_label=intent,
                detected_entities=[],
                confidence_score=0.7 if intent != 'CHITCHAT' else 0.5,
                reasoning="Fallback keyword-based detection"
            )

    intent_parser = FallbackIntentParser()

try:
    response_generator = ResponseGenerator()
    logger.info("Initialized ResponseGenerator with configured LLM provider")
except Exception as e:
    logger.warning(f"Failed to initialize ResponseGenerator with configured LLM: {e}. Responses will use fallback text generation.")
    response_generator = None

uncertainty_detector = UncertaintyDetector()


class ChatRequest(BaseModel):
    """聊天请求结构（支持多轮对话）"""
    merchant_id: Optional[str] = "default"
    user_query: str
    conversation_history: Optional[List[dict]] = None
    conversation_id: Optional[str] = None  # 新增：会话 ID


class ChatResponse(BaseModel):
    """聊天响应结构（包含会话追踪）"""
    merchant_id: str
    user_query: str
    response_text: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    sources: Optional[List[str]] = None
    is_clarification_triggered: bool = False
    conversation_id: Optional[str] = None  # 新增：会话 ID
    timestamp: datetime = None  # 新增：响应时间戳
    
    def __init__(self, **data):
        if data.get("timestamp") is None:
            data["timestamp"] = datetime.now()
        super().__init__(**data)


@router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest) -> ChatResponse:
    """
    主聊天端点：端到端工作流，支持多轮对话
    
    流程：
    1. 获取或创建会话
    2. 添加用户消息到会话历史
    3. 意图解析 (Intent Parser)
    4. 混合检索 (Structured Data + RAG)
    5. 不确定性检测 (Uncertainty Detector)
    6. 条件分支：
       - 若不确定 → 触发澄清流程
       - 若确定 → 调用 LLM 生成回答
    7. 将响应添加到会话历史
    8. 返回响应（包含会话 ID）
    """
    try:
        merchant_id = request.merchant_id
        user_query = request.user_query
        
        # 【第0阶段】会话管理：获取或创建会话
        conversation_id = _get_or_create_conversation(
            conversation_id=request.conversation_id,
            merchant_id=merchant_id
        )
        
        # 添加用户消息到会话历史
        _add_message_to_conversation(conversation_id, "user", user_query)
        
        logger.info(f"Processing query for merchant={merchant_id}, conversation={conversation_id}, query='{user_query}'")
        
        # 【第 1 阶段】意图解析
        intent_result = intent_parser.parse(user_query)
        intent_type = intent_result.intent_label
        intent_confidence = intent_result.confidence_score
        detected_entities = intent_result.detected_entities
        
        # 更新会话中的最后意图
        conversation_data = storage_manager.get_conversation(conversation_id)
        if conversation_data:
            conversation_data["last_intent"] = intent_type
            storage_manager.save_conversation(conversation_id, conversation_data)
            storage_manager.update_conversation_metadata(conversation_id, {"last_intent": intent_type})
        
        print(f"DEBUG: Query='{user_query}', Intent={intent_type}, Confidence={intent_confidence}")
        logger.info(f"Intent parsed: {intent_type}, confidence: {intent_confidence}")
        
        # 【第 2 阶段】混合检索
        retrieval_results = await retrieve_knowledge(
            merchant_id=merchant_id,
            query=user_query,
            intent_type=intent_type,
            entities=detected_entities
        )
        retrieved_docs = retrieval_results["documents"]
        retrieval_scores = retrieval_results["scores"]

        # 如果存在结构化数据但向量检索得分较弱，则补充高置信度信号
        if retrieval_results.get("structured_data") and not retrieval_scores:
            retrieval_scores = [1.0]
            retrieved_docs = [
                {
                    "content": _format_structured_data(retrieval_results["structured_data"]),
                    "metadata": {},
                    "source": "structured_data"
                }
            ]

        # 【第 3 阶段】不确定性检测
        uncertainty_result = UncertaintyDetector.detect(
            retrieval_scores=retrieval_scores,
            retrieved_documents=retrieved_docs,
            user_query=user_query,
            intent_confidence=intent_confidence
        )
        # 【第 4 阶段】条件分支 + 澄清防抖（避免重复澄清循环）
        if uncertainty_result.is_uncertain:
            # 获取会话元信息，检查最近是否已触发澄清
            conversation_data = storage_manager.get_conversation(conversation_id) or {}
            last_clarify_iso = conversation_data.get('last_clarification_time')
            last_clarify_query = conversation_data.get('last_clarification_query')
            recently_clarified = False

            try:
                if last_clarify_iso:
                    last_clarify_dt = datetime.fromisoformat(last_clarify_iso)
                    if datetime.now() - last_clarify_dt < timedelta(seconds=120):
                        # 简单相似度：基于共享词数比例
                        if last_clarify_query:
                            a = set(re.findall(r"\w+", last_clarify_query.lower()))
                            b = set(re.findall(r"\w+", user_query.lower()))
                            overlap = 0.0
                            if a or b:
                                overlap = len(a & b) / max(1, len(a | b))
                            if overlap > 0.6:
                                recently_clarified = True
            except Exception:
                recently_clarified = False

            if recently_clarified:
                # 避免再次澄清：尝试给出谨慎答案并提示人工接入或更多信息
                grounded_response = await generate_grounded_response(
                    user_query=user_query,
                    retrieval_results=retrieval_results,
                    merchant_id=merchant_id
                )

                response_text = (
                    "我刚刚向您请求过更多信息，但还没有收到额外细节。\n"
                    "下面是我基于现有资料的尽力回答（如有不准请补充信息或联系人工客服）：\n\n"
                    + grounded_response
                )

                # 标记为非澄清触发（已尝试退化回答）
                response = ChatResponse(
                    merchant_id=merchant_id,
                    user_query=user_query,
                    response_text=response_text,
                    intent=intent_type,
                    confidence=uncertainty_result.confidence_score,
                    is_clarification_triggered=False,
                    conversation_id=conversation_id,
                )
            else:
                # 在触发澄清之前，先请求 LLM 给出自评置信度，作为二次判定信号
                try:
                    generated_text, llm_confidence = await response_generator.generate_grounded_response_with_confidence(
                        user_query=user_query,
                        retrieval_results=retrieval_results,
                        merchant_id=merchant_id,
                    )

                    # 重新使用不确定性检测器进行判定（加入 LLM 自评置信度）
                    combined_uncertainty = UncertaintyDetector.detect(
                        retrieval_scores=retrieval_scores,
                        retrieved_documents=retrieved_docs,
                        user_query=user_query,
                        intent_confidence=intent_confidence,
                        llm_confidence=llm_confidence,
                    )

                    if combined_uncertainty.is_uncertain:
                        # 仍然不确定 -> 触发澄清
                        clarification_prompt = build_clarification_prompt(
                            user_query,
                            combined_uncertainty.recommendation,
                            possible_intents=["产品咨询", "政策咨询", "订单服务"]
                        )

                        # 更新会话元数据
                        try:
                            conversation_data = storage_manager.get_conversation(conversation_id) or {}
                            conversation_data['last_clarification_time'] = datetime.now().isoformat()
                            conversation_data['last_clarification_query'] = user_query
                            conversation_data['clarification_count'] = conversation_data.get('clarification_count', 0) + 1
                            storage_manager.save_conversation(conversation_id, conversation_data)
                        except Exception:
                            logger.debug('Failed to save clarification metadata')

                        response = ChatResponse(
                            merchant_id=merchant_id,
                            user_query=user_query,
                            response_text=clarification_prompt,
                            intent=intent_type,
                            confidence=combined_uncertainty.confidence_score,
                            is_clarification_triggered=True,
                            conversation_id=conversation_id,
                        )
                    else:
                        # LLM 自评显示可信，可直接返回之前生成的答案
                        response = ChatResponse(
                            merchant_id=merchant_id,
                            user_query=user_query,
                            response_text=generated_text,
                            intent=intent_type,
                            confidence=combined_uncertainty.confidence_score,
                            sources=[doc["source"] for doc in retrieved_docs if doc.get("source")],
                            is_clarification_triggered=False,
                            conversation_id=conversation_id,
                        )

                except Exception as e:
                    logger.exception(f"Failed to generate LLM self-eval: {e}")
                    # 回退到原始澄清流程
                    clarification_prompt = build_clarification_prompt(
                        user_query,
                        uncertainty_result.recommendation,
                        possible_intents=["产品咨询", "政策咨询", "订单服务"]
                    )
                    response = ChatResponse(
                        merchant_id=merchant_id,
                        user_query=user_query,
                        response_text=clarification_prompt,
                        intent=intent_type,
                        confidence=intent_confidence,
                        is_clarification_triggered=True,
                        conversation_id=conversation_id,
                    )
        else:
            # 生成回答
            grounded_response = await generate_grounded_response(
                user_query=user_query,
                retrieval_results=retrieval_results,
                merchant_id=merchant_id
            )
            response = ChatResponse(
                merchant_id=merchant_id,
                user_query=user_query,
                response_text=grounded_response,
                intent=intent_type,
                confidence=uncertainty_result.confidence_score,
                sources=[doc["source"] for doc in retrieved_docs if doc.get("source")],
                is_clarification_triggered=False,
                conversation_id=conversation_id,
            )
        
        # 【第 5 阶段】添加响应到会话历史
        _add_message_to_conversation(conversation_id, "assistant", response.response_text)
        
        return response

    except Exception as e:
        logger.exception(f"Error in chat_query: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def retrieve_knowledge(
    merchant_id: str,
    query: str,
    intent_type: str,
    entities: dict
) -> dict:
    """
    从向量库检索相关知识，支持混合检索（结构化数据 + RAG）

    接口设计：
    - 输入：商家 ID、查询字符串、意图类型、实体列表
    - 输出：文档片段 + 相似度分数 + 结构化数据（如果适用）

    混合检索逻辑：
    1. 如果是结构化问题（价格、库存、订单），优先查询适配器
    2. 如果适配器未命中或需要补充，走向量检索
    3. 返回统一格式的结果
    """
    results = {
        "documents": [],
        "scores": [],
        "structured_data": None,
        "retrieval_type": "rag"  # "structured", "hybrid", or "rag"
    }

    # 1. 检查是否需要结构化数据查询
    structured_result = None
    if intent_type in ["PRODUCT_INQUIRY", "ORDER_SERVICE", "POLICY_INQUIRY"]:
        # 尝试从适配器获取结构化数据
        structured_result = await _query_structured_data(merchant_id, query, intent_type, entities)
        if structured_result:
            results["structured_data"] = structured_result
            results["retrieval_type"] = "structured"

    # 2. 向量检索（总是执行，作为补充或主要检索）
    try:
        try:
            logger.info("Attempting to initialize engine retriever...")
            if not engine.retrievers:
                engine.initialize()
            retriever = engine.get_retriever(merchant_id)
            reranker = Reranker()
            logger.info("Successfully initialized retriever from engine")
        except Exception as e:
            logger.warning(f"Failed to initialize engine retriever: {e}. Falling back to local retriever.")
            try:
                retriever = Retriever(merchant_id=merchant_id, top_k=settings.similarity_top_k)
                reranker = Reranker()
                logger.info("Successfully initialized local Retriever")
            except Exception as inner_e:
                logger.warning(f"Failed to initialize local Retriever: {inner_e}. Using LocalTextEmbeddings fallback.")
                retriever = Retriever(merchant_id=merchant_id, embedder=LocalTextEmbeddings(), top_k=settings.similarity_top_k)
                reranker = Reranker()
                logger.warning("Using LocalTextEmbeddings fallback for similarity search")

        search_results = retriever.retrieve(query, k=settings.similarity_top_k)
        ranked_results = reranker.rerank(search_results, query)

        for doc, score in ranked_results:
            results["documents"].append({
                "content": doc["content"],
                "metadata": doc["metadata"],
                "source": doc.get("source", "unknown")
            })
            results["scores"].append(score)

        if structured_result and results["documents"]:
            results["retrieval_type"] = "hybrid"
        elif structured_result:
            results["retrieval_type"] = "structured"

    except Exception as e:
        logger.warning(f"Vector retrieval failed: {e}")
        # 如果向量检索失败，至少返回结构化数据
        if structured_result:
            results["retrieval_type"] = "structured"

    return results


async def _query_structured_data(merchant_id: str, query: str, intent_type: str, entities: list) -> Optional[dict]:
    """
    查询结构化数据适配器

    Args:
        merchant_id: 商家ID
        query: 原始查询
        intent_type: 意图类型
        entities: 提取的实体

    Returns:
        结构化数据字典或 None
    """
    try:
        # 从实体中提取产品名、订单号或政策类型
        product_name = None
        order_id = None
        policy_type = None

        # 优先使用实体抽取结果
        for entity in entities:
            if "《" in entity and "》" in entity:  # 书名特征
                product_name = entity
            elif "ORDER" in entity.upper() or (entity.isdigit() and len(entity) >= 3):
                order_id = entity
            elif entity.lower() in ["return", "refund", "shipping", "warranty", "policy"]:
                policy_type = entity.lower()

        # 如果没有识别出实体，则从查询中尝试提取
        if not product_name and intent_type == "PRODUCT_INQUIRY":
            titles = re.findall(r'《([^》]+)》', query)
            if titles:
                product_name = f'《{titles[0]}》'
            else:
                for candidate in ["《三体》", "《Java编程思想》", "《百年孤独》"]:
                    if candidate.replace('《', '').replace('》', '') in query:
                        product_name = candidate
                        break

        if not order_id and intent_type == "ORDER_SERVICE":
            order_match = re.search(r'(ORDER\d+|\d{6,12})', query, re.IGNORECASE)
            if order_match:
                order_id = order_match.group(0)

        # 政策类型提取
        if intent_type == "POLICY_INQUIRY" and not policy_type:
            policy_keyword_map = {
                "return": ["退货", "退回", "refund"],
                "shipping": ["运费", "快递", "邮费", "delivery", "shipping"],
                "warranty": ["保修", "保障", "warranty", "guarantee"],
                "refund": ["退款", "返款", "refund"]
            }
            for key, keywords in policy_keyword_map.items():
                if any(keyword in query for keyword in keywords):
                    policy_type = key
                    break
            if not policy_type:
                policy_type = "return"

        # 根据意图类型查询相应数据
        if intent_type == "PRODUCT_INQUIRY":
            if product_name:
                price_data = mock_adapter.get_product_price(merchant_id, product_name)
                inventory_data = mock_adapter.get_inventory(merchant_id, product_name)

                if price_data or inventory_data:
                    return {
                        "product_name": product_name,
                        "price": price_data,
                        "inventory": inventory_data
                    }

        elif intent_type == "ORDER_SERVICE":
            if order_id:
                order_data = mock_adapter.get_order_status(merchant_id, order_id)
                shipping_data = mock_adapter.get_shipping_info(merchant_id, order_id)

                if order_data:
                    return {
                        "order_id": order_id,
                        "status": order_data,
                        "shipping": shipping_data
                    }

        elif intent_type == "POLICY_INQUIRY":
            if policy_type:
                policy_data = mock_adapter.get_policy(merchant_id, policy_type)
                if policy_data:
                    return {
                        "policy_type": policy_type,
                        "policy": policy_data
                    }

        return None

    except Exception as e:
        logger.warning(f"Structured data query failed: {e}")
        return None


async def generate_grounded_response(
    user_query: str,
    retrieval_results: dict,
    merchant_id: str
) -> str:
    """
    基于检索文档和结构化数据的 LLM 回答生成

    核心约束（对应论文"实证生成"概念）：
    - 必须从 retrieval_results 中引用内容
    - 每个要点必须标注来源
    - 若文档中不存在，绝不编造
    - 优先使用结构化数据，确保准确性

    Args:
        user_query: 用户原始查询
        retrieval_results: retrieve_knowledge 的返回结果
        merchant_id: 商家ID

    Returns:
        生成的回答文本
    """
    try:
        # 准备上下文信息
        context_parts = []

        # 1. 添加结构化数据（如果有）
        structured_data = retrieval_results.get("structured_data")
        if structured_data:
            context_parts.append("=== 结构化数据 ===")
            context_parts.append(_format_structured_data(structured_data))

        # 2. 添加文档检索结果
        documents = retrieval_results.get("documents", [])
        if documents:
            context_parts.append("=== 相关文档 ===")
            for i, doc in enumerate(documents[:3]):  # 限制前3个最相关文档
                context_parts.append(f"文档 {i+1}: {doc['content']}")
                if doc.get('source'):
                    context_parts.append(f"来源: {doc['source']}")

        # 3. 构建 Prompt
        context_text = "\n\n".join(context_parts)

        system_prompt = f"""
        你是一个专业的电商客服助手。请基于提供的上下文信息回答用户问题。

        回答要求：
        1. 必须基于上下文信息回答，不得编造信息
        2. 如果上下文中有结构化数据（价格、库存等），优先使用这些准确数据
        3. 引用文档内容时，要标注来源
        4. 如果问题无法从上下文中完全回答，要明确说明
        5. 回答要友好、专业、有帮助

        上下文信息：
        {context_text}
        """

        if response_generator:
            try:
                return await response_generator.generate_grounded_response(
                    user_query=user_query,
                    retrieval_results=retrieval_results,
                    merchant_id=merchant_id,
                )
            except Exception as e:
                logger.warning(f"LLM generation failed: {e}")

        return _generate_mock_response(user_query, structured_data, documents)

    except Exception as e:
        logger.exception(f"Error generating response: {e}")
        return f"抱歉，暂时无法生成回答。请稍后重试。错误：{str(e)}"


def _format_structured_data(data: dict) -> str:
    """
    格式化结构化数据为可读文本

    Args:
        data: 结构化数据字典

    Returns:
        格式化的文本
    """
    lines = []

    if "product_name" in data:
        lines.append(f"产品：{data['product_name']}")

    if "price" in data and data["price"]:
        price_info = data["price"]
        lines.append(f"价格：{price_info.get('price', '未知')} {price_info.get('currency', 'CNY')}")

    if "inventory" in data and data["inventory"]:
        inv_info = data["inventory"]
        status_map = {
            "in_stock": "有货",
            "low_stock": "库存紧张",
            "out_of_stock": "缺货"
        }
        status = status_map.get(inv_info.get("status", "unknown"), "未知")
        quantity = inv_info.get("quantity", "未知")
        lines.append(f"库存：{quantity} 件 ({status})")

    if "order_id" in data:
        lines.append(f"订单号：{data['order_id']}")

    if "status" in data and data["status"]:
        status_info = data["status"]
        status = status_info.get("status", "未知")
        tracking = status_info.get("tracking_number", "")
        delivery = status_info.get("estimated_delivery", "")
        lines.append(f"订单状态：{status}")
        if tracking:
            lines.append(f"快递单号：{tracking}")
        if delivery:
            lines.append(f"预计送达：{delivery}")

    if "shipping" in data and data["shipping"]:
        ship_info = data["shipping"]
        carrier = ship_info.get("carrier", "")
        cost = ship_info.get("shipping_cost", "")
        if carrier:
            lines.append(f"快递公司：{carrier}")
        if cost:
            lines.append(f"运费：{cost} 元")

    return "\n".join(lines)


def _generate_mock_response(user_query: str, structured_data: Optional[dict], documents: list) -> str:
    """
    本地模板回答生成器（用于无 OpenAI Key 或 API 调用失败时）。
    """
    if structured_data:
        parts = ["依据系统中的结构化信息："]
        parts.append(_format_structured_data(structured_data))
        parts.append("\n如果您需要更多细节，请告诉我。")
        return "\n".join(parts)

    if documents:
        summary = "; \n".join([f"来自{doc.get('source', 'unknown')}的内容：{doc['content']}" for doc in documents[:2]])
        return f"我在相关文档中找到了以下信息：\n{summary}" \
               "\n如果这些信息仍不能完全回答您的问题，请提供更多细节。"

    return "抱歉，我暂时无法直接回答这个问题。请提供更多上下文信息，例如商品名称或订单号。"


def build_clarification_prompt(user_query: str, recommendation: str, possible_intents: list) -> str:
    """
    构建澄清提示

    Args:
        user_query: 用户原始查询
        recommendation: 不确定性检测器的推荐
        possible_intents: 可能的意图列表

    Returns:
        澄清提示文本
    """
    intent_options = "\n".join([f"- {intent}" for intent in possible_intents])

    prompt = f"""
抱歉，我对您的查询 "{user_query}" 理解不够清楚。

{recommendation}

为了更好地帮助您，请告诉我您想要咨询的是以下哪方面的内容：
{intent_options}

或者您可以提供更多详细信息，我会为您提供更准确的回答。
"""

    return prompt.strip()


# ==================== 会话管理端点 ====================

@router.get("/conversations/{conversation_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    conversation_id: str,
    limit: int = 10,
    offset: int = 0,
) -> ConversationHistoryResponse:
    """
    获取会话历史

    Args:
        conversation_id: 会话 ID
        limit: 返回消息数上限（默认 10）
        offset: 偏移量（默认 0）

    Returns:
        会话历史响应
    """
    try:
        # 检查会话是否存在
        conversation_data = storage_manager.get_conversation(conversation_id)
        if not conversation_data:
            raise HTTPException(status_code=404, detail=f"会话 {conversation_id} 不存在")

        # 获取消息历史
        messages = storage_manager.get_messages(conversation_id, limit, offset)

        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            merchant_id=conversation_data.get("merchant_id"),
            messages=messages,
            total_count=conversation_data.get("message_count", 0),
            returned_count=len(messages)
        )
        
        # 转换为 ConversationMessage 对象
        messages = [
            ConversationMessage(
                role=msg["role"],
                content=msg["content"],
                timestamp=msg.get("timestamp"),
            )
            for msg in returned_messages
        ]
        
        return ConversationHistoryResponse(
            conversation_id=conversation_id,
            merchant_id=conversation["merchant_id"],
            messages=messages,
            total_count=len(all_messages),
            returned_count=len(messages),
        )
    
    except HTTPException as e:
        raise
    except Exception as e:
        logger.exception(f"Error in get_conversation_history: {e}")
        raise HTTPException(status_code=500, detail=f"获取历史失败: {str(e)}")


@router.get("/conversations/{conversation_id}")
async def get_conversation_info(conversation_id: str) -> dict:
    """
    获取会话信息

    Args:
        conversation_id: 会话 ID

    Returns:
        会话信息
    """
    try:
        # 获取会话数据
        conversation_data = storage_manager.get_conversation(conversation_id)
        if not conversation_data:
            raise HTTPException(status_code=404, detail=f"会话 {conversation_id} 不存在")

        # 获取元数据（如果有）
        metadata = storage_manager.get_conversation_metadata(conversation_id) or {}

        return {
            "conversation_id": conversation_id,
            "merchant_id": conversation_data.get("merchant_id"),
            "message_count": conversation_data.get("message_count", 0),
            "created_at": conversation_data.get("created_at"),
            "last_updated": conversation_data.get("last_updated"),
            "last_intent": conversation_data.get("last_intent"),
            "status": conversation_data.get("status", "active"),
        }

    except HTTPException as e:
        raise
    except Exception as e:
        logger.exception(f"Error in get_conversation_info: {e}")
        raise HTTPException(status_code=500, detail=f"获取信息失败: {str(e)}")


@router.post("/conversations/{conversation_id}/close")
async def close_conversation(
    conversation_id: str,
    reason: Optional[str] = None,
) -> dict:
    """
    关闭会话

    Args:
        conversation_id: 会话 ID
        reason: 关闭原因

    Returns:
        关闭结果
    """
    try:
        # 检查会话是否存在
        conversation_data = storage_manager.get_conversation(conversation_id)
        if not conversation_data:
            raise HTTPException(status_code=404, detail=f"会话 {conversation_id} 不存在")

        # 更新会话状态
        conversation_data["status"] = "closed"
        conversation_data["last_updated"] = datetime.now().isoformat()

        storage_manager.save_conversation(conversation_id, conversation_data)
        storage_manager.update_conversation_metadata(conversation_id, {
            "status": "closed",
            "last_updated": conversation_data["last_updated"]
        })

        logger.info(f"Conversation {conversation_id} closed. Reason: {reason}")

        return {
            "conversation_id": conversation_id,
            "status": "closed",
            "message": "会话已关闭",
        }

    except HTTPException as e:
        raise
        raise
    except Exception as e:
        logger.exception(f"Error in close_conversation: {e}")
        raise HTTPException(status_code=500, detail=f"关闭失败: {str(e)}")


@router.get("/conversations")
async def list_conversations(merchant_id: Optional[str] = None) -> dict:
    """
    列出所有会话

    Args:
        merchant_id: 可选的商家 ID 筛选

    Returns:
        会话列表
    """
    try:
        # 获取会话列表
        conversation_ids = storage_manager.list_conversations(merchant_id)

        result = []
        for conv_id in conversation_ids:
            conversation_data = storage_manager.get_conversation(conv_id)
            if conversation_data:
                result.append({
                    "conversation_id": conv_id,
                    "merchant_id": conversation_data.get("merchant_id"),
                    "message_count": conversation_data.get("message_count", 0),
                    "created_at": conversation_data.get("created_at"),
                    "last_updated": conversation_data.get("last_updated"),
                    "last_intent": conversation_data.get("last_intent"),
                    "status": conversation_data.get("status", "active"),
                })

        return {
            "total": len(result),
            "conversations": result,
        }

    except Exception as e:
        logger.exception(f"Error in list_conversations: {e}")
        raise HTTPException(status_code=500, detail=f"列表查询失败: {str(e)}")


@router.get("/health")
async def chat_health():
    """聊天模块健康检查"""
    try:
        # 获取存储统计信息
        stats = storage_manager.get_stats()

        # 计算活跃会话数
        active_conversations = 0
        conversation_ids = storage_manager.list_conversations()
        for conv_id in conversation_ids:
            conv_data = storage_manager.get_conversation(conv_id)
            if conv_data and conv_data.get("status") == "active":
                active_conversations += 1

        return {
            "status": "healthy",
            "module": "chat",
            "active_conversations": active_conversations,
            "total_conversations": len(conversation_ids),
            "storage": stats
        }
    except Exception as e:
        logger.exception(f"Error in chat_health: {e}")
        return {
            "status": "unhealthy",
            "module": "chat",
            "error": str(e)
        }
