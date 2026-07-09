"""Customer-service workflow orchestration."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from app.agent.intent_parser import IntentParser, IntentSchema
from app.agent.product_recommender import ProductRecommender
from app.agent.response_generator import ResponseGenerator
from app.agent.uncertainty_detector import UncertaintyDetector, UncertaintyResult
from app.config import settings
from app.connectors import mock_adapter
from app.rag.reranker import Reranker
from app.rag.retriever import Retriever
from app.storage.product_store import product_store

logger = logging.getLogger(__name__)

COMMERCE_INTENTS = {"PRODUCT_INQUIRY", "POLICY_INQUIRY", "ORDER_SERVICE"}


def _query_terms(query: str) -> List[str]:
    groups = {
        "return": ["退货", "无理由", "return"],
        "refund": ["退款", "仅退款", "refund"],
        "shipping": ["运费", "包邮", "物流", "快递", "shipping", "delivery"],
        "invoice": ["发票", "抬头", "税号", "invoice"],
        "size": ["尺码", "尺寸", "身高", "体重", "肩宽", "size"],
        "recommend": ["推荐", "适合", "适用", "年龄", "岁", "recommend"],
        "stock": ["库存", "有货", "现货", "stock", "inventory"],
        "price": ["价格", "多少钱", "费用", "price"],
        "order": ["订单", "单号", "发货", "order", "tracking"],
    }

    terms: List[str] = []
    lowered = query.lower()
    for keywords in groups.values():
        for keyword in keywords:
            if keyword in query or keyword in lowered:
                terms.append(keyword)

    stopwords = {"how", "can", "the", "this", "that", "to", "for", "with", "what", "issued", "issue"}
    terms.extend(
        token for token in re.findall(r"[A-Za-z0-9_-]{3,}", lowered) if token not in stopwords
    )
    return list(dict.fromkeys(terms))


@dataclass
class RetrievalBundle:
    documents: List[Dict[str, Any]] = field(default_factory=list)
    scores: List[float] = field(default_factory=list)
    structured_data: Optional[Dict[str, Any]] = None
    retrieval_type: str = "none"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "documents": self.documents,
            "scores": self.scores,
            "structured_data": self.structured_data,
            "retrieval_type": self.retrieval_type,
        }

    @property
    def evidence_sources(self) -> List[Dict[str, Any]]:
        evidence: List[Dict[str, Any]] = []
        if self.structured_data:
            recommendation = self.structured_data.get("product_recommendation") or {}
            for item in (recommendation.get("recommendations") or [])[:3]:
                evidence.append(
                    {
                        "type": "product_recommendation",
                        "source": "product_store",
                        "title": item.get("title"),
                        "product_id": item.get("product_id"),
                        "platform": item.get("platform"),
                        "shop_id": item.get("shop_id"),
                        "sku": item.get("sku"),
                        "price": item.get("price"),
                        "stock": item.get("stock"),
                        "score": item.get("score"),
                        "preview": "; ".join([str(reason) for reason in item.get("reasons", [])][:3]),
                    }
                )
            evidence.append(
                {
                    "type": "structured_data",
                    "source": self.structured_data.get("source", "structured_data"),
                    "title": self.structured_data.get("product_name") or self.structured_data.get("matched_product_title"),
                    "product_id": self.structured_data.get("product_id") or self.structured_data.get("matched_product_id"),
                    "platform": self.structured_data.get("platform"),
                    "shop_id": self.structured_data.get("shop_id"),
                    "sku": self.structured_data.get("sku"),
                    "preview": str(
                        self.structured_data.get("description")
                        or self.structured_data.get("policy")
                        or self.structured_data.get("matched_product_source")
                        or ""
                    )[:220],
                }
            )

        for doc, score in zip(self.documents, self.scores):
            metadata = doc.get("metadata") or {}
            evidence.append(
                {
                    "type": "rag_chunk",
                    "source": doc.get("source") or metadata.get("source") or "unknown",
                    "score": score,
                    "product_id": metadata.get("product_id"),
                    "platform": metadata.get("platform"),
                    "shop_id": metadata.get("shop_id"),
                    "chunk_index": metadata.get("chunk_index"),
                    "preview": str(doc.get("content") or "")[:220],
                    "metadata": metadata,
                }
            )
        return evidence[:8]

    @property
    def sources(self) -> List[str]:
        seen: set[str] = set()
        values: List[str] = []
        for doc in self.documents:
            source = doc.get("source")
            if source and source not in seen:
                seen.add(source)
                values.append(source)
        if self.structured_data and "structured_data" not in seen:
            values.append("structured_data")
        return values

    @property
    def top_score(self) -> float:
        return max(self.scores) if self.scores else 0.0

    @property
    def has_usable_context(self) -> bool:
        return bool(self.structured_data) or self.top_score >= settings.retrieval_confidence_threshold

    def focus_score(self, query: str) -> int:
        terms = _query_terms(query)
        if not terms or not self.documents:
            return 0

        score = 0
        for doc in self.documents[:4]:
            content = str(doc.get("content", "")).lower()
            for term in terms:
                if term.lower() in content:
                    score += 2
            if any(char.isdigit() for char in content) and any(char.isdigit() for char in query):
                score += 1
        return score


@dataclass
class RiskAssessment:
    level: str = "low"
    requires_human_review: bool = False
    reasons: List[str] = field(default_factory=list)
    missing_info: List[str] = field(default_factory=list)


@dataclass
class WorkflowResult:
    merchant_id: str
    user_query: str
    effective_query: str
    response_text: str
    intent: str
    confidence: float
    sources: List[str] = field(default_factory=list)
    is_clarification_triggered: bool = False
    risk_level: str = "low"
    auto_send_allowed: bool = False
    auto_send_blockers: List[str] = field(default_factory=list)
    requires_human_review: bool = False
    handoff_reason: Optional[str] = None
    missing_info: List[str] = field(default_factory=list)
    retrieval_type: str = "none"
    evidence_sources: List[Dict[str, Any]] = field(default_factory=list)
    debug: Dict[str, Any] = field(default_factory=dict)

    def to_chat_response_payload(self, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        payload = {
            "merchant_id": self.merchant_id,
            "user_query": self.user_query,
            "response_text": self.response_text,
            "intent": self.intent,
            "confidence": self.confidence,
            "sources": self.sources,
            "is_clarification_triggered": self.is_clarification_triggered,
            "recommended_reply": self.response_text,
            "risk_level": self.risk_level,
            "auto_send_allowed": self.auto_send_allowed,
            "auto_send_blockers": self.auto_send_blockers,
            "requires_human_review": self.requires_human_review,
            "handoff_reason": self.handoff_reason,
            "missing_info": self.missing_info,
            "retrieval_type": self.retrieval_type,
            "evidence_sources": self.evidence_sources,
        }
        if conversation_id:
            payload["conversation_id"] = conversation_id
        return payload


class CustomerServiceWorkflow:
    def __init__(
        self,
        intent_parser: Optional[IntentParser] = None,
        response_generator: Optional[ResponseGenerator] = None,
        uncertainty_detector: Optional[UncertaintyDetector] = None,
        reranker: Optional[Reranker] = None,
        product_recommender: Optional[ProductRecommender] = None,
    ) -> None:
        self.intent_parser = intent_parser or IntentParser()
        self.response_generator = response_generator or ResponseGenerator()
        self.uncertainty_detector = uncertainty_detector or UncertaintyDetector()
        self.reranker = reranker or Reranker()
        self.product_recommender = product_recommender or ProductRecommender()

    async def run(
        self,
        merchant_id: str,
        user_query: str,
        conversation_history: Optional[Sequence[Dict[str, Any]]] = None,
        page_context: Optional[Dict[str, Any]] = None,
        rule_config: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        merchant_id = merchant_id or "default"
        user_query = (user_query or "").strip()
        effective_query = self._build_effective_query(user_query, conversation_history)

        if not user_query:
            return self._clarification_result(
                merchant_id=merchant_id,
                user_query=user_query,
                effective_query=effective_query,
                intent="OTHERS",
                confidence=0.0,
                reason="EMPTY_QUERY",
            )

        intent_result = self.intent_parser.parse(effective_query)
        retrieval = await self.retrieve(
            merchant_id=merchant_id,
            query=effective_query,
            intent=intent_result,
            page_context=page_context,
        )
        uncertainty = self._detect_uncertainty(effective_query, intent_result, retrieval)
        risk = self._assess_risk(effective_query, intent_result, retrieval)

        if (
            intent_result.intent_label == "OTHERS"
            and intent_result.confidence_score < 0.6
            and not retrieval.structured_data
        ):
            return self._blocked_result(
                merchant_id=merchant_id,
                user_query=user_query,
                effective_query=effective_query,
                intent=intent_result.intent_label,
                confidence=min(uncertainty.confidence_score, intent_result.confidence_score),
                reason="; ".join(risk.reasons) if risk.reasons else "问题意图不明确，当前资料不足以自动回复",
                missing_info=["clear_customer_service_question"],
                blocker="intent_not_clear",
                retrieval=retrieval,
                risk_level=risk.level if risk.level != "low" else "medium",
            )

        if self._should_handoff_for_low_quality_evidence(effective_query, intent_result, retrieval):
            return self._blocked_result(
                merchant_id=merchant_id,
                user_query=user_query,
                effective_query=effective_query,
                intent=intent_result.intent_label,
                confidence=min(uncertainty.confidence_score, retrieval.top_score),
                reason="检索到的资料和买家问题不够匹配，不适合自动回复",
                missing_info=["focused_merchant_evidence"],
                blocker="evidence_not_focused",
                retrieval=retrieval,
                risk_level=risk.level if risk.level != "low" else "medium",
            )

        if self._should_clarify(effective_query, uncertainty, retrieval):
            result = self._clarification_result(
                merchant_id=merchant_id,
                user_query=user_query,
                effective_query=effective_query,
                intent=intent_result.intent_label,
                confidence=uncertainty.confidence_score,
                reason=uncertainty.recommendation,
                sources=retrieval.sources,
            )
            result.risk_level = risk.level
            result.requires_human_review = risk.requires_human_review
            result.handoff_reason = "; ".join(risk.reasons) if risk.reasons else result.handoff_reason
            result.missing_info = risk.missing_info or result.missing_info
            result.retrieval_type = retrieval.retrieval_type
            result.auto_send_blockers = self._auto_send_blockers(
                confidence=result.confidence,
                risk=result.risk_level,
                requires_human_review=result.requires_human_review,
                is_clarification=True,
                missing_info=result.missing_info,
                retrieval=retrieval,
                query=effective_query,
                page_context=page_context,
                rule_config=rule_config,
            )
            result.auto_send_allowed = False
            return result

        response_text = await self._generate_response(
            merchant_id=merchant_id,
            query=effective_query,
            intent=intent_result,
            retrieval=retrieval,
        )

        confidence = max(0.0, min(1.0, uncertainty.confidence_score or retrieval.top_score))
        if retrieval.structured_data and confidence < 0.65:
            confidence = 0.65

        blockers = self._auto_send_blockers(
            confidence=confidence,
            risk=risk.level,
            requires_human_review=risk.requires_human_review,
            is_clarification=False,
            missing_info=risk.missing_info,
            retrieval=retrieval,
            query=effective_query,
            page_context=page_context,
            rule_config=rule_config,
        )
        rule_reasons = self._rule_handoff_reasons(
            query=effective_query,
            blockers=blockers,
            risk=risk,
            rule_config=rule_config,
        )
        handoff_reasons = [*risk.reasons, *rule_reasons]

        return WorkflowResult(
            merchant_id=merchant_id,
            user_query=user_query,
            effective_query=effective_query,
            response_text=response_text,
            intent=intent_result.intent_label,
            confidence=confidence,
            sources=retrieval.sources,
            is_clarification_triggered=False,
            risk_level=risk.level,
            auto_send_allowed=not blockers,
            auto_send_blockers=blockers,
            requires_human_review=risk.requires_human_review or bool(blockers),
            handoff_reason="; ".join(handoff_reasons) if handoff_reasons else None,
            missing_info=risk.missing_info,
            retrieval_type=retrieval.retrieval_type,
            evidence_sources=retrieval.evidence_sources,
            debug={
                "intent_reasoning": intent_result.reasoning,
                "retrieval_scores": retrieval.scores,
                "uncertainty": uncertainty.__dict__,
                "focus_score": retrieval.focus_score(effective_query),
                "rag_product_filter": (retrieval.structured_data or {}).get("product_id"),
                "recommendation_count": len(
                    ((retrieval.structured_data or {}).get("product_recommendation") or {}).get("recommendations", [])
                ),
            },
        )

    async def retrieve(
        self,
        merchant_id: str,
        query: str,
        intent: IntentSchema,
        page_context: Optional[Dict[str, Any]] = None,
    ) -> RetrievalBundle:
        page_context = page_context or {}
        structured_data = self._structured_from_page_context(merchant_id, page_context)
        adapter_data = self._query_structured_data(merchant_id, query, intent)
        if structured_data and adapter_data:
            structured_data = {**adapter_data, **structured_data}
        elif adapter_data:
            structured_data = adapter_data

        recommendation_data = self.product_recommender.recommend(
            merchant_id=merchant_id,
            query=query,
            platform=page_context.get("platform"),
            shop_id=page_context.get("shop_id"),
        )
        if recommendation_data:
            if structured_data:
                structured_data = {**structured_data, "product_recommendation": recommendation_data}
            else:
                structured_data = {
                    "source": "product_recommender",
                    "product_recommendation": recommendation_data,
                }

        documents: List[Dict[str, Any]] = []
        scores: List[float] = []
        try:
            retriever = Retriever(merchant_id=merchant_id)
            # Pass product_id (if matched from page_context) for RAG filtering
            product_id = (structured_data or {}).get("product_id")
            search_results = retriever.retrieve(
                query,
                k=settings.similarity_top_k,
                product_id=product_id,
                platform=page_context.get("platform"),
                shop_id=page_context.get("shop_id"),
            )
            ranked_results = self.reranker.rerank(search_results, query)
            for doc, score in ranked_results:
                documents.append(
                    {
                        "content": doc.get("content", ""),
                        "metadata": doc.get("metadata", {}),
                        "source": doc.get("source", "unknown"),
                    }
                )
                scores.append(score)
        except Exception as exc:
            logger.warning("Vector retrieval failed for merchant=%s: %s", merchant_id, exc)

        if structured_data and documents:
            retrieval_type = "hybrid"
        elif structured_data:
            retrieval_type = "structured"
        elif documents:
            retrieval_type = "rag"
        else:
            retrieval_type = "none"

        return RetrievalBundle(
            documents=documents,
            scores=scores,
            structured_data=structured_data,
            retrieval_type=retrieval_type,
        )

    def _detect_uncertainty(
        self,
        query: str,
        intent: IntentSchema,
        retrieval: RetrievalBundle,
    ) -> UncertaintyResult:
        clear_commerce_intent = (
            intent.intent_label in COMMERCE_INTENTS
            and intent.confidence_score >= 0.75
            and not self._is_vague_query(query)
        )
        if retrieval.has_usable_context and (clear_commerce_intent or retrieval.structured_data):
            retrieval_confidence = max(retrieval.top_score, 0.65)
            return UncertaintyResult(
                is_uncertain=False,
                confidence_score=retrieval_confidence * max(intent.confidence_score, 0.75),
                retrieval_confidence=retrieval_confidence,
                query_ambiguity_score=0.0,
                recommendation="CONFIDENT: usable merchant context found",
            )

        return self.uncertainty_detector.detect(
            retrieval_scores=retrieval.scores,
            retrieved_documents=retrieval.documents,
            user_query=query,
            intent_confidence=intent.confidence_score,
        )

    def _should_clarify(
        self,
        query: str,
        uncertainty: UncertaintyResult,
        retrieval: RetrievalBundle,
    ) -> bool:
        if retrieval.structured_data:
            return False
        if self._is_vague_query(query):
            return True
        if retrieval.top_score >= settings.retrieval_confidence_threshold:
            return False
        return UncertaintyDetector.should_trigger_clarification(uncertainty)

    def _should_handoff_for_low_quality_evidence(
        self,
        query: str,
        intent: IntentSchema,
        retrieval: RetrievalBundle,
    ) -> bool:
        if retrieval.structured_data:
            return False
        if intent.intent_label not in COMMERCE_INTENTS:
            return False
        if not retrieval.documents:
            return True
        return retrieval.focus_score(query) < 2

    def _auto_send_blockers(
        self,
        confidence: float,
        risk: str,
        requires_human_review: bool,
        is_clarification: bool,
        missing_info: Sequence[str],
        retrieval: RetrievalBundle,
        query: str,
        page_context: Optional[Dict[str, Any]] = None,
        rule_config: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        blockers: List[str] = []
        mode = str((rule_config or {}).get("mode") or "dry_run")
        confidence_threshold = self._rule_confidence_threshold(rule_config)
        if is_clarification:
            blockers.append("clarification_required")
        if mode != "auto":
            blockers.append(f"mode_{mode}")
        if risk == "high":
            blockers.append("risk_high")
        elif risk == "medium" and self._rule_enabled(rule_config, "after_sale", True) and not settings.auto_send_allow_medium_risk:
            blockers.append(f"risk_{risk}")
        if requires_human_review:
            blockers.append("human_review_required")
        if missing_info:
            blockers.append("missing_info")
        if confidence < confidence_threshold and self._rule_enabled(rule_config, "low_confidence", True):
            blockers.append("low_confidence")
        if not retrieval.structured_data and not retrieval.documents and self._rule_enabled(rule_config, "out_of_knowledge", True):
            blockers.append("no_evidence")
        if retrieval.documents and not retrieval.structured_data and retrieval.focus_score(query) < 2:
            blockers.append("low_evidence_focus")
        if self._matches_sensitive_word(query, rule_config):
            blockers.append("sensitive_word")
        if self._rule_enabled(rule_config, "keyword", True) and self._matches_handoff_keyword(query, rule_config):
            blockers.append("handoff_keyword")
        if self._rule_enabled(rule_config, "image", True) and self._looks_like_image_message(page_context):
            blockers.append("image_message")
        return list(dict.fromkeys(blockers))

    def _rule_enabled(
        self,
        rule_config: Optional[Dict[str, Any]],
        key: str,
        default: bool = True,
    ) -> bool:
        rules = (rule_config or {}).get("handoff_rules") or {}
        return bool(rules.get(key, default))

    def _rule_confidence_threshold(self, rule_config: Optional[Dict[str, Any]]) -> float:
        value = (rule_config or {}).get("confidence_threshold", settings.auto_send_min_confidence)
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return settings.auto_send_min_confidence

    def _matches_sensitive_word(self, query: str, rule_config: Optional[Dict[str, Any]]) -> bool:
        words = (rule_config or {}).get("sensitive_words") or []
        return self._contains_risk_term(query, [str(item) for item in words if str(item).strip()])

    def _matches_handoff_keyword(self, query: str, rule_config: Optional[Dict[str, Any]]) -> bool:
        words = (rule_config or {}).get("handoff_keywords") or []
        return self._contains_risk_term(query, [str(item) for item in words if str(item).strip()])

    def _looks_like_image_message(self, page_context: Optional[Dict[str, Any]]) -> bool:
        if not page_context:
            return False
        message_type = str(page_context.get("message_type") or page_context.get("content_type") or "").lower()
        if message_type in {"image", "photo", "picture"}:
            return True
        if page_context.get("has_image") is True:
            return True
        try:
            return int(page_context.get("image_count") or 0) > 0
        except (TypeError, ValueError):
            return False

    def _rule_handoff_reasons(
        self,
        query: str,
        blockers: Sequence[str],
        risk: RiskAssessment,
        rule_config: Optional[Dict[str, Any]],
    ) -> List[str]:
        reasons: List[str] = []
        blocker_set = set(blockers)
        if any(item.startswith("mode_") for item in blocker_set):
            reasons.append("当前接待模式不允许自动发送")
        if "handoff_keyword" in blocker_set:
            reasons.append("命中转人工关键词")
        if "sensitive_word" in blocker_set:
            reasons.append("命中平台敏感词或联系方式风险")
        if "image_message" in blocker_set:
            reasons.append("图片消息需要人工确认")
        if "low_confidence" in blocker_set:
            reasons.append("AI 置信度低于规则阈值")
        if "no_evidence" in blocker_set or "low_evidence_focus" in blocker_set:
            reasons.append("当前知识库证据不足")
        if "risk_medium" in blocker_set and risk.level == "medium":
            reasons.append("售后、订单或退款类问题按规则转人工")
        if "risk_high" in blocker_set:
            reasons.append("高风险问题必须转人工")
        if self._matches_handoff_keyword(query, rule_config) and "handoff_keyword" not in blocker_set:
            reasons.append("命中关键词但当前规则未启用自动转人工")
        return list(dict.fromkeys(reasons))

    async def _generate_response(
        self,
        merchant_id: str,
        query: str,
        intent: IntentSchema,
        retrieval: RetrievalBundle,
    ) -> str:
        if intent.intent_label == "CHITCHAT":
            return "您好，请问有什么可以帮您？"

        if retrieval.structured_data:
            recommendation_reply = self._build_recommendation_reply(retrieval.structured_data)
            if recommendation_reply:
                return recommendation_reply
            direct_reply = self._build_structured_reply(query, retrieval.structured_data)
            if direct_reply:
                return direct_reply

        if not retrieval.has_usable_context and intent.intent_label != "CHITCHAT":
            return "抱歉，当前店铺资料里还没有足够可靠的信息，建议转人工确认或补充相关资料。"

        try:
            return await self.response_generator.generate_grounded_response(
                user_query=query,
                retrieval_results=retrieval.as_dict(),
                merchant_id=merchant_id,
            )
        except Exception as exc:
            logger.exception("Response generation failed: %s", exc)

        return "抱歉，暂时无法生成可靠回复，建议转人工确认。"

    def _build_recommendation_reply(self, data: Dict[str, Any]) -> Optional[str]:
        recommendation = data.get("product_recommendation") or {}
        products = recommendation.get("recommendations") or []
        if not products:
            return None

        lines = ["\u53ef\u4ee5\u4f18\u5148\u770b\u8fd9\u51e0\u6b3e\uff1a"]
        for index, product in enumerate(products[:3], start=1):
            title = product.get("title") or "\u672a\u547d\u540d\u5546\u54c1"
            price = product.get("price")
            stock = product.get("stock")
            reasons = product.get("reasons") or []
            parts = [f"{index}. {title}"]
            if price not in (None, ""):
                parts.append(f"\u4ef7\u683c {price}")
            if stock not in (None, ""):
                parts.append(f"\u5e93\u5b58 {stock}")
            if reasons:
                parts.append("\u539f\u56e0\uff1a" + "\uff1b".join(str(item) for item in reasons[:2]))
            lines.append("\uff0c".join(parts))
        lines.append("\u5982\u679c\u60a8\u6709\u9884\u7b97\u3001\u7528\u9014\u6216\u504f\u597d\uff0c\u6211\u53ef\u4ee5\u518d\u5e2e\u60a8\u7f29\u5c0f\u8303\u56f4\u3002")
        return "\n".join(lines)

    def _query_structured_data(
        self,
        merchant_id: str,
        query: str,
        intent: IntentSchema,
    ) -> Optional[Dict[str, Any]]:
        product_id = self._extract_product_id(query, intent.detected_entities)
        order_id = self._extract_order_id(query, intent.detected_entities)
        policy_type = self._extract_policy_type(query)

        try:
            if intent.intent_label == "PRODUCT_INQUIRY" and product_id:
                price = mock_adapter.get_product_price(merchant_id, product_id)
                inventory = mock_adapter.get_inventory(merchant_id, product_id)
                if price or inventory:
                    return {"product_name": product_id, "price": price, "inventory": inventory}

            if intent.intent_label == "ORDER_SERVICE" and order_id:
                status = mock_adapter.get_order_status(merchant_id, order_id)
                shipping = mock_adapter.get_shipping_info(merchant_id, order_id)
                if status or shipping:
                    return {"order_id": order_id, "status": status, "shipping": shipping}

            if intent.intent_label == "POLICY_INQUIRY" and policy_type:
                policy = mock_adapter.get_policy(merchant_id, policy_type)
                if policy:
                    return {"policy_type": policy_type, "policy": policy}
        except Exception as exc:
            logger.warning("Structured adapter query failed: %s", exc)

        return None

    def _structured_from_page_context(
        self,
        merchant_id: str,
        page_context: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not page_context:
            return None

        product_name = page_context.get("product_name") or page_context.get("title") or page_context.get("name")
        if not product_name:
            return None

        data: Dict[str, Any] = {"product_name": product_name, "source": "browser_page_context"}
        for key in ("sku", "url", "platform", "shop_id", "platform_product_id"):
            if page_context.get(key):
                data[key] = page_context[key]
        if page_context.get("price"):
            data["price"] = {"price": page_context["price"], "currency": page_context.get("currency", "CNY")}
        if page_context.get("stock") or page_context.get("inventory"):
            data["inventory"] = {
                "quantity": page_context.get("stock") or page_context.get("inventory"),
                "status": page_context.get("stock_status", "in_stock"),
            }

        # --- NEW: try to match the page context to a local product record ---
        try:
            matched = product_store.find_by_context(
                merchant_id=merchant_id or "default",
                platform=page_context.get("platform"),
                platform_product_id=page_context.get("platform_product_id"),
                sku=page_context.get("sku"),
                title=product_name,
                shop_id=page_context.get("shop_id"),
            )
            if matched:
                data["matched_product_id"] = matched["id"]
                data["matched_product_title"] = matched.get("title", "")
                data["matched_product_source"] = matched.get("source_type", "")
                # Also pull the local product_id for downstream RAG filtering
                data["product_id"] = matched["id"]
                # Pull product description for answering when no dedicated doc exists
                matched_desc = matched.get("description")
                if matched_desc:
                    data["product_description"] = matched_desc
                    data["description"] = matched_desc
                logger.info(
                    "Matched page context -> product %s (%s)",
                    matched["id"], matched.get("title", ""),
                )
            else:
                logger.debug("Page context did not match any local product")
        except Exception as exc:
            logger.warning("Product match from page_context failed (non-fatal): %s", exc)
        # -------------------------------------------------------------------

        return data

    def _assess_risk(
        self,
        query: str,
        intent: IntentSchema,
        retrieval: RetrievalBundle,
    ) -> RiskAssessment:
        high_risk_terms = [
            "投诉", "差评", "赔偿", "起诉", "违法", "隐私", "身份证", "银行卡",
            "平台介入", "仅退款", "假货", "欺诈",
            "complaint", "complain", "compensation", "compensate", "lawsuit", "sue",
            "illegal", "privacy", "personal data", "id card", "bank card", "chargeback",
            "platform intervention", "negative review", "bad review", "fake", "counterfeit",
            "fraud", "scam", "deceptive", "report you",
        ]
        medium_risk_terms = [
            "退款", "退货", "换货", "发票", "催发货", "改地址", "订单", "售后",
            "return", "refund", "exchange", "invoice", "receipt", "order", "tracking",
            "delivery delay", "change address", "after-sale", "after sales", "afterservice",
        ]

        reasons: List[str] = []
        missing_info: List[str] = []

        if self._contains_risk_term(query, high_risk_terms):
            reasons.append("问题包含投诉、赔偿、平台介入或合规相关风险")
            level = "high"
        elif self._contains_risk_term(query, medium_risk_terms) or intent.intent_label == "ORDER_SERVICE":
            reasons.append("问题涉及订单、退款、发票、物流或售后处理")
            level = "medium"
        else:
            level = "low"

        if intent.intent_label == "ORDER_SERVICE" and not self._extract_order_id(query, intent.detected_entities):
            missing_info.append("order_id")
        if not retrieval.has_usable_context and intent.intent_label in COMMERCE_INTENTS:
            missing_info.append("merchant_knowledge")

        return RiskAssessment(
            level=level,
            requires_human_review=level == "high" or bool(missing_info),
            reasons=reasons,
            missing_info=missing_info,
        )

    def _contains_risk_term(self, query: str, terms: Sequence[str]) -> bool:
        lowered = query.casefold()
        return any(term in query or term.casefold() in lowered for term in terms)

    def _blocked_result(
        self,
        merchant_id: str,
        user_query: str,
        effective_query: str,
        intent: str,
        confidence: float,
        reason: str,
        missing_info: List[str],
        blocker: str,
        retrieval: RetrievalBundle,
        risk_level: str = "medium",
    ) -> WorkflowResult:
        response = (
            f"抱歉，我对“{user_query}”还没有足够把握。"
            "为避免误导买家，建议转人工确认，或补充更明确的商品、订单、政策资料。"
        )
        blockers = [blocker, "human_review_required"]
        if risk_level != "low":
            blockers.append(f"risk_{risk_level}")
        if confidence < 0.5:
            blockers.append("low_confidence")
        return WorkflowResult(
            merchant_id=merchant_id,
            user_query=user_query,
            effective_query=effective_query,
            response_text=response,
            intent=intent,
            confidence=max(0.0, min(1.0, confidence)),
            sources=retrieval.sources if blocker != "intent_not_clear" else [],
            is_clarification_triggered=True,
            risk_level=risk_level,
            auto_send_allowed=False,
            auto_send_blockers=list(dict.fromkeys(blockers)),
            requires_human_review=True,
            handoff_reason=reason,
            missing_info=missing_info,
            retrieval_type=retrieval.retrieval_type,
            evidence_sources=retrieval.evidence_sources,
        )

    def _clarification_result(
        self,
        merchant_id: str,
        user_query: str,
        effective_query: str,
        intent: str,
        confidence: float,
        reason: str,
        sources: Optional[List[str]] = None,
    ) -> WorkflowResult:
        response = (
            f"抱歉，我对“{user_query}”还没有足够把握。\n\n"
            "为了更准确地回复买家，请补充以下信息之一：\n"
            "- 具体商品名称、SKU 或当前商品页\n"
            "- 订单号或物流信息\n"
            "- 店铺规则里对应的退换货、运费或售后条款\n\n"
            "如果这是退款、投诉、赔偿或平台介入问题，建议先转人工确认。"
        )
        return WorkflowResult(
            merchant_id=merchant_id,
            user_query=user_query,
            effective_query=effective_query,
            response_text=response,
            intent=intent,
            confidence=confidence,
            sources=sources or [],
            is_clarification_triggered=True,
            risk_level="medium",
            auto_send_allowed=False,
            auto_send_blockers=["clarification_required"],
            requires_human_review=True,
            handoff_reason=reason,
            missing_info=["more_context"],
        )

    def _build_effective_query(
        self,
        user_query: str,
        conversation_history: Optional[Sequence[Dict[str, Any]]],
    ) -> str:
        choice = user_query.strip().lower()
        clarification_choices = {"产品咨询", "商品咨询", "政策咨询", "订单服务", "product", "policy", "order"}
        if choice not in clarification_choices or not conversation_history:
            return user_query

        previous_user = [
            str(item.get("content", ""))
            for item in conversation_history
            if item.get("role") == "user" and item.get("content") != user_query
        ]
        if not previous_user:
            return user_query
        return f"{previous_user[-1]}。补充意图：{user_query}"

    def _is_vague_query(self, query: str) -> bool:
        compact = re.sub(r"\s+", "", query)
        vague_patterns = {
            "这个呢？", "这个呢", "有吗？", "有吗", "怎么弄？", "怎么弄",
            "怎么办？", "怎么办", "可以吗？", "可以吗", "多少钱？", "多少钱",
        }
        return compact in vague_patterns or len(compact) <= 4

    def _extract_product_id(self, query: str, entities: Sequence[str]) -> Optional[str]:
        if entities:
            return entities[0]
        title = re.search(r"[《\"“]([^》\"”]+)[》\"”]", query)
        if title:
            return title.group(1)
        sku = re.search(r"\b[A-Z0-9][A-Z0-9_-]{2,}\b", query, re.I)
        if sku:
            return sku.group(0)
        return None

    def _extract_order_id(self, query: str, entities: Sequence[str]) -> Optional[str]:
        for entity in entities:
            if re.search(r"(ORDER\d+|\d{6,20})", entity, re.I):
                return entity
        match = re.search(r"(ORDER\d+|\d{6,20})", query, re.I)
        return match.group(0) if match else None

    def _extract_policy_type(self, query: str) -> Optional[str]:
        policy_keywords = {
            "return": ["退货", "退换", "七天无理由", "return"],
            "refund": ["退款", "仅退款", "refund"],
            "shipping": ["运费", "包邮", "物流", "快递", "shipping", "delivery"],
            "warranty": ["保修", "质保", "售后保障", "warranty"],
            "invoice": ["发票", "invoice"],
        }
        lowered = query.lower()
        for policy_type, keywords in policy_keywords.items():
            if any(keyword in query or keyword in lowered for keyword in keywords):
                return policy_type
        return None

    def _format_structured_data(self, data: Dict[str, Any]) -> str:
        lines: List[str] = []
        if data.get("product_name"):
            lines.append(f"商品：{data['product_name']}")
        if data.get("sku"):
            lines.append(f"SKU：{data['sku']}")
        if data.get("price"):
            price = data["price"]
            if isinstance(price, dict):
                lines.append(f"价格：{price.get('price', '未知')} {price.get('currency', 'CNY')}")
            else:
                lines.append(f"价格：{price}")
        if data.get("inventory"):
            inventory = data["inventory"]
            if isinstance(inventory, dict):
                lines.append(f"库存：{inventory.get('quantity', '未知')} ({inventory.get('status', 'unknown')})")
            else:
                lines.append(f"库存：{inventory}")
        if data.get("order_id"):
            lines.append(f"订单号：{data['order_id']}")
        if data.get("status"):
            lines.append(f"订单状态：{data['status']}")
        if data.get("shipping"):
            lines.append(f"物流信息：{data['shipping']}")
        if data.get("policy"):
            lines.append(f"店铺政策：{data['policy']}")
        product_desc = data.get("description") or data.get("product_description")
        if product_desc:
            lines.append(f"商品详情：{product_desc[:500]}")
        return "\n".join(lines)

    def _build_structured_reply(self, query: str, data: Dict[str, Any]) -> Optional[str]:
        query_lower = query.lower()
        product_name = data.get("product_name")
        reply_parts: List[str] = []

        if product_name:
            reply_parts.append(f"这款商品是 {product_name}。")
        if data.get("sku"):
            reply_parts.append(f"SKU 是 {data['sku']}。")

        if data.get("price") and any(word in query_lower or word in query for word in ["price", "价格", "多少钱", "费用"]):
            price = data["price"]
            if isinstance(price, dict):
                reply_parts.append(f"当前价格是 {price.get('price', '未知')} {price.get('currency', 'CNY')}。")
            else:
                reply_parts.append(f"当前价格是 {price}。")

        if data.get("inventory") and any(word in query_lower or word in query for word in ["stock", "库存", "有货", "现货"]):
            inventory = data["inventory"]
            if isinstance(inventory, dict):
                reply_parts.append(f"当前库存是 {inventory.get('quantity', '未知')}，状态为 {inventory.get('status', 'unknown')}。")
            else:
                reply_parts.append(f"当前库存是 {inventory}。")

        if data.get("status"):
            reply_parts.append(f"订单状态：{data['status']}。")
        if data.get("shipping"):
            reply_parts.append(f"物流信息：{data['shipping']}。")
        if data.get("policy"):
            policy = data["policy"]
            if isinstance(policy, dict):
                for key in ("title", "description", "condition", "detail", "delivery_time"):
                    if policy.get(key):
                        reply_parts.append(str(policy[key]))
            else:
                reply_parts.append(str(policy))

        # If a product description is available and the user is asking about
        # product details, include it as context
        product_desc = data.get("description") or data.get("product_description")
        if product_desc and not reply_parts:
            reply_parts.append(f"商品介绍：{product_desc}")
        elif product_desc and any(word in query_lower for word in ["说明", "介绍", "材质", "什么", "可以", "能", "规格", "功能", "怎么"]):
            reply_parts.append(f"商品介绍：{product_desc}")

        if not reply_parts and data:
            reply_parts.append("根据当前结构化资料：")
            reply_parts.append(self._format_structured_data(data))
        return "\n".join(reply_parts) if reply_parts else None


default_workflow = CustomerServiceWorkflow()
