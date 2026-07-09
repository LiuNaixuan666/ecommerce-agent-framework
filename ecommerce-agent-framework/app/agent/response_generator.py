"""Grounded response generation for ecommerce customer service."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.llm.factory import get_llm


class ResponseGenerator:
    """Generate customer-service replies from retrieved merchant context.

    This class deliberately avoids product-specific or test-document-specific
    rules. It prepares clean evidence for the configured LLM and provides a
    conservative local fallback when the LLM is unavailable.
    """

    def __init__(self, llm=None):
        self.llm = llm or get_llm()
        self.logger = logging.getLogger(__name__)

    async def generate_grounded_response(
        self,
        user_query: str,
        retrieval_results: dict,
        merchant_id: str,
    ) -> str:
        context_text = self._build_context(retrieval_results)
        if not context_text:
            return self._no_evidence_reply()

        messages = self._build_messages(user_query=user_query, context_text=context_text, with_confidence=False)

        try:
            response_text = self.llm.chat(
                messages,
                max_tokens=settings.llm_max_tokens,
                temperature=min(settings.llm_temperature, 0.4),
            )
            response_text = (response_text or "").strip()
            if response_text:
                return response_text
        except Exception as exc:
            self.logger.warning("LLM generation failed: %s", exc)

        structured_data = retrieval_results.get("structured_data")
        documents = retrieval_results.get("documents", [])
        return self._fallback_response(user_query, structured_data, documents)

    async def generate_grounded_response_with_confidence(
        self,
        user_query: str,
        retrieval_results: dict,
        merchant_id: str,
    ) -> Tuple[str, float]:
        context_text = self._build_context(retrieval_results)
        if not context_text:
            return self._no_evidence_reply(), 0.2

        messages = self._build_messages(user_query=user_query, context_text=context_text, with_confidence=True)

        try:
            raw = self.llm.chat(
                messages,
                max_tokens=settings.llm_max_tokens,
                temperature=min(settings.llm_temperature, 0.3),
            )
            answer, confidence = self._parse_confidence_response(raw)
            if answer:
                return answer, confidence
        except Exception as exc:
            self.logger.warning("LLM generation with confidence failed: %s", exc)

        fallback = self._fallback_response(
            user_query,
            retrieval_results.get("structured_data"),
            retrieval_results.get("documents", []),
        )
        return fallback, 0.55 if fallback != self._no_evidence_reply() else 0.2

    def _build_messages(self, user_query: str, context_text: str, with_confidence: bool) -> List[Dict[str, str]]:
        if with_confidence:
            output_rule = (
                'Return strict JSON only: {"answer": "...", "self_confidence": 0.0}. '
                "self_confidence should reflect whether the supplied evidence directly answers the buyer."
            )
        else:
            output_rule = "Return only the reply text. Do not include hidden analysis."

        system_prompt = (
            "You are an ecommerce customer-service assistant.\n"
            "Answer only from the supplied merchant context. Do not invent facts.\n"
            "If the evidence is insufficient, say that the issue should be transferred to a human agent or needs more information.\n"
            "Keep the reply concise, friendly, and suitable to send to a buyer.\n"
            "Prefer exact numbers and policy terms from the evidence.\n"
            "Mention the source file names briefly when useful.\n"
            f"{output_rule}\n\n"
            "Context:\n"
            f"{context_text}"
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User Query: {user_query}"},
        ]

    def _build_context(self, retrieval_results: dict) -> str:
        parts: List[str] = []

        structured_data = retrieval_results.get("structured_data")
        if structured_data:
            formatted = self._format_structured_data(structured_data)
            if formatted:
                parts.append("Structured Data:\n" + formatted)

        documents = retrieval_results.get("documents", [])
        for index, doc in enumerate(documents[:4], start=1):
            content = self._clean_text(str(doc.get("content", "")))
            if not content:
                continue
            source = doc.get("source") or doc.get("metadata", {}).get("source") or "unknown"
            parts.append(f"Document {index} | source: {source}\n{content[:1200]}")

        return "\n\n".join(parts).strip()

    def _format_structured_data(self, data: Dict[str, Any]) -> str:
        lines: List[str] = []
        normalized = dict(data)

        if normalized.get("price") and not isinstance(normalized["price"], dict):
            normalized["price"] = {"price": normalized["price"], "currency": ""}
        if normalized.get("stock") and not normalized.get("inventory"):
            normalized["inventory"] = {"quantity": normalized["stock"], "status": "in_stock"}

        if normalized.get("product_name"):
            lines.append(f"Product: {normalized['product_name']}")
        if normalized.get("sku"):
            lines.append(f"SKU: {normalized['sku']}")
        if normalized.get("price"):
            price = normalized["price"]
            lines.append(f"Price: {price.get('price', 'unknown')} {price.get('currency', 'CNY')}".strip())
        if normalized.get("inventory"):
            inventory = normalized["inventory"]
            lines.append(
                f"Inventory: {inventory.get('quantity', 'unknown')} ({inventory.get('status', 'unknown')})"
            )
        if normalized.get("order_id"):
            lines.append(f"Order ID: {normalized['order_id']}")
        if normalized.get("status"):
            lines.append(f"Order status: {normalized['status']}")
        if normalized.get("shipping"):
            lines.append(f"Shipping: {normalized['shipping']}")
        if normalized.get("policy"):
            lines.append(f"Policy: {normalized['policy']}")

        return "\n".join(lines)

    def _fallback_response(
        self,
        user_query: str,
        structured_data: Optional[dict],
        documents: List[dict],
    ) -> str:
        if structured_data:
            formatted = self._format_structured_data(structured_data)
            if formatted:
                return "根据当前店铺资料：\n" + formatted

        evidence = self._select_focused_evidence(user_query, documents)
        if not evidence:
            return self._no_evidence_reply()

        lines = ["根据当前店铺资料，可以这样回复："]
        for item in evidence:
            lines.append(f"- {item['text']}")
        sources = self._format_sources([item["source"] for item in evidence])
        if sources:
            lines.append(sources)
        return "\n".join(lines)

    def _select_focused_evidence(self, user_query: str, documents: List[dict]) -> List[Dict[str, str]]:
        query_terms = self._query_terms(user_query)
        if not query_terms:
            return []

        scored: List[Tuple[int, Dict[str, str]]] = []
        for doc in documents[:5]:
            source = str(doc.get("source") or "unknown")
            for sentence in self._split_sentences(str(doc.get("content", ""))):
                sentence = self._clean_text(sentence)
                if not sentence or self._looks_like_wrapper_text(sentence):
                    continue
                score = self._score_sentence(sentence, query_terms)
                if score >= 3:
                    scored.append((score, {"text": sentence, "source": source}))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected: List[Dict[str, str]] = []
        seen_text: set[str] = set()
        for _, item in scored:
            if item["text"] in seen_text:
                continue
            selected.append(item)
            seen_text.add(item["text"])
            if len(selected) >= 3:
                break
        return selected

    def _query_terms(self, query: str) -> List[str]:
        groups = {
            "return": ["退货", "无理由", "return"],
            "refund": ["退款", "仅退款", "refund"],
            "shipping": ["运费", "包邮", "物流", "快递", "shipping", "delivery"],
            "invoice": ["发票", "抬头", "税号", "invoice"],
            "size": ["尺码", "尺寸", "身高", "体重", "肩宽", "size"],
            "recommend": ["推荐", "适合", "适用", "年龄", "岁", "recommend"],
            "stock": ["库存", "有货", "现货", "stock", "inventory"],
            "price": ["价格", "多少钱", "费用", "price"],
        }

        terms: List[str] = []
        lowered = query.lower()
        for keywords in groups.values():
            for keyword in keywords:
                if keyword in query or keyword in lowered:
                    terms.append(keyword)

        stopwords = {"how", "can", "the", "this", "that", "to", "for", "with", "what", "issued", "issue"}
        terms.extend(
            token
            for token in re.findall(r"[A-Za-z0-9_-]{3,}", lowered)
            if token not in stopwords
        )
        return list(dict.fromkeys(terms))

    def _score_sentence(self, sentence: str, query_terms: List[str]) -> int:
        lowered = sentence.lower()
        score = 0
        for term in query_terms:
            if term in sentence or term in lowered:
                score += 3
        if re.search(r"\d+", sentence):
            score += 1
        if any(word in sentence for word in ["支持", "不支持", "可以", "需要", "建议", "规则", "政策", "适合"]):
            score += 1
        return score

    def _split_sentences(self, text: str) -> List[str]:
        lines = []
        for line in (text or "").splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("Document ") or line.startswith("Structured Data:") or line.startswith("Context:"):
                continue
            lines.append(line)
        cleaned = self._clean_text(" ".join(lines))
        cleaned = re.sub(r"\s+(?=Q:)", "\n", cleaned)
        cleaned = re.sub(r"\s+(?=A:)", "\n", cleaned)
        return [
            part.strip()
            for part in re.split(r"(?<=[。！？!?；;])\s*|(?<=\.)\s+(?=[A-Z\u4e00-\u9fff])|\n+|(?:\s+-\s+)", cleaned)
            if part.strip()
        ]

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text or "")
        return text.strip()

    def _looks_like_wrapper_text(self, sentence: str) -> bool:
        wrappers = [
            "Document ",
            "source:",
            "User Query",
            "用户问题",
            "Context:",
            "Structured Data:",
        ]
        if any(wrapper in sentence for wrapper in wrappers):
            return True
        return sentence.startswith("Q:")

    def _format_sources(self, sources: List[str]) -> str:
        deduped: List[str] = []
        for source in sources:
            if source and source not in deduped:
                deduped.append(source)
        if not deduped:
            return ""
        return "信息来源：" + "、".join(deduped) + "。"

    def _parse_confidence_response(self, raw: str) -> Tuple[str, float]:
        text = (raw or "").strip()
        if not text:
            return "", 0.0

        try:
            payload = json.loads(text)
            answer = str(payload.get("answer") or payload.get("response") or "").strip()
            confidence = float(payload.get("self_confidence", 0.5))
            return answer, max(0.0, min(1.0, confidence))
        except Exception:
            pass

        match = re.search(r"\{.*\}\s*$", text, re.S)
        if match:
            try:
                payload = json.loads(match.group(0))
                answer = str(payload.get("answer") or text[: match.start()]).strip()
                confidence = float(payload.get("self_confidence", 0.5))
                return answer, max(0.0, min(1.0, confidence))
            except Exception:
                pass

        return text, 0.5

    def _no_evidence_reply(self) -> str:
        return "抱歉，当前店铺资料里没有找到足够可靠的依据。为避免误导买家，建议转人工确认或补充相关商品/政策资料。"
