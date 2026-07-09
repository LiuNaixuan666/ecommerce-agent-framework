"""Local fallback LLM for offline development."""

from __future__ import annotations

import json
import re
from typing import Dict, List, Tuple

from app.llm.base import BaseLLM


class LocalLLMClient(BaseLLM):
    """Small conservative local fallback.

    It does not know any merchant-specific facts. It only classifies simple
    ecommerce intent prompts and summarizes the supplied context.
    """

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        prompt = "\n".join(message.get("content", "") for message in messages)

        if self._is_intent_prompt(prompt):
            return self._classify_intent(prompt)

        question = self._extract_question(prompt)
        context = self._extract_context(prompt)
        answer, confidence = self._answer_from_context(question, context)

        if "self_confidence" in prompt:
            return json.dumps(
                {"answer": answer, "self_confidence": confidence},
                ensure_ascii=False,
            )
        return answer

    def _is_intent_prompt(self, prompt: str) -> bool:
        return "intent_label" in prompt and "PRODUCT_INQUIRY" in prompt

    def _classify_intent(self, prompt: str) -> str:
        question = self._extract_question(prompt)
        lowered = question.lower()

        if self._contains_any(question, lowered, ["订单", "物流", "发货", "快递", "单号", "order", "tracking"]):
            intent = "ORDER_SERVICE"
            confidence = 0.82
        elif self._contains_any(
            question,
            lowered,
            ["退货", "退款", "换货", "运费", "包邮", "售后", "发票", "return", "refund", "shipping", "invoice"],
        ):
            intent = "POLICY_INQUIRY"
            confidence = 0.82
        elif self._contains_any(
            question,
            lowered,
            ["商品", "产品", "价格", "库存", "有货", "尺码", "推荐", "介绍", "sku", "price", "stock", "size"],
        ):
            intent = "PRODUCT_INQUIRY"
            confidence = 0.82
        elif self._contains_any(question, lowered, ["你好", "您好", "hello", "hi", "谢谢"]):
            intent = "CHITCHAT"
            confidence = 0.7
        else:
            intent = "OTHERS"
            confidence = 0.45

        return json.dumps(
            {
                "intent_label": intent,
                "detected_entities": self._extract_entities(question),
                "confidence_score": confidence,
                "reasoning": "Local fallback intent classification",
            },
            ensure_ascii=False,
        )

    def _contains_any(self, original: str, lowered: str, keywords: List[str]) -> bool:
        return any(keyword in original or keyword in lowered for keyword in keywords)

    def _extract_entities(self, text: str) -> List[str]:
        entities: List[str] = []
        entities.extend(re.findall(r"[《\"“]([^》\"”]{1,80})[》\"”]", text))
        entities.extend(re.findall(r"\b[A-Z0-9][A-Z0-9_-]{2,}\b", text, re.I))
        entities.extend(re.findall(r"\b(?:ORDER)?\d{6,20}\b", text, re.I))

        deduped: List[str] = []
        for entity in entities:
            entity = entity.strip()
            if entity and entity not in deduped:
                deduped.append(entity)
        return deduped

    def _extract_question(self, prompt: str) -> str:
        patterns = [
            r"(?:用户问题|User Query)[:：]\s*['\"]?(.+?)['\"]?(?:\n|$)",
            r"(?:买家问题|问题)[:：]\s*(.+?)(?:\n|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt, re.S)
            if match:
                return match.group(1).strip()
        return ""

    def _extract_context(self, prompt: str) -> str:
        markers = ["Context:", "上下文信息", "相关文档", "结构化数据"]
        for marker in markers:
            if marker in prompt:
                context = prompt.split(marker, 1)[1].strip(" ：:\n")
                for question_marker in ["\n用户问题", "\nUser Query", "\n买家问题"]:
                    if question_marker in context:
                        context = context.split(question_marker, 1)[0]
                return context.strip(" ：:\n")
        return ""

    def _answer_from_context(self, question: str, context: str) -> Tuple[str, float]:
        if not context or len(context.strip()) < 20:
            return (
                "抱歉，当前没有检索到可用的本地资料。为避免误导买家，建议转人工确认或补充相关资料。",
                0.25,
            )

        evidence = self._select_evidence(question, context)
        if not evidence:
            return (
                "抱歉，当前店铺资料里没有找到能直接回答这个问题的明确依据。建议转人工确认或补充相关资料。",
                0.4,
            )

        sources = self._extract_sources(context)
        lines = ["根据当前店铺资料，可以这样回复："]
        lines.extend(f"- {item}" for item in evidence)
        if sources:
            lines.append("信息来源：" + "、".join(sources) + "。")
        else:
            lines.append("信息来源：本地知识库。")
        confidence = 0.78 if len(evidence) >= 2 else 0.62
        return "\n".join(lines), confidence

    def _select_evidence(self, question: str, context: str) -> List[str]:
        terms = self._query_terms(question)
        if not terms:
            return []

        scored: List[Tuple[int, str]] = []
        for sentence in self._split_sentences(context):
            if self._looks_like_wrapper_text(sentence):
                continue
            score = self._score_sentence(sentence, terms)
            if score >= 3:
                scored.append((score, sentence))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected: List[str] = []
        for _, sentence in scored:
            if sentence not in selected:
                selected.append(sentence)
            if len(selected) >= 3:
                break
        return selected

    def _query_terms(self, query: str) -> List[str]:
        groups = [
            ["退货", "无理由", "return"],
            ["退款", "仅退款", "refund"],
            ["运费", "包邮", "物流", "快递", "shipping", "delivery"],
            ["发票", "抬头", "税号", "invoice"],
            ["尺码", "尺寸", "身高", "体重", "肩宽", "size"],
            ["推荐", "适合", "适用", "年龄", "岁", "recommend"],
            ["库存", "有货", "现货", "stock", "inventory"],
            ["价格", "多少钱", "费用", "price"],
        ]
        lowered = query.lower()
        terms: List[str] = []
        for keywords in groups:
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

    def _score_sentence(self, sentence: str, terms: List[str]) -> int:
        lowered = sentence.lower()
        score = 0
        for term in terms:
            if term in sentence or term in lowered:
                score += 3
        if re.search(r"\d+", sentence):
            score += 1
        if any(word in sentence for word in ["支持", "不支持", "可以", "需要", "建议", "规则", "政策", "适合"]):
            score += 1
        return score

    def _split_sentences(self, context: str) -> List[str]:
        text = context or ""
        lines = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("Document ") or line.startswith("Structured Data:") or line.startswith("Context:"):
                continue
            lines.append(line)

        cleaned = " ".join(lines)
        cleaned = re.sub(r"\s+", " ", cleaned)
        cleaned = re.sub(r"\s+(?=Q:)", "\n", cleaned)
        cleaned = re.sub(r"\s+(?=A:)", "\n", cleaned)
        parts = re.split(r"(?<=[。！？!?；;])\s*|(?<=\.)\s+(?=[A-Z\u4e00-\u9fff])|\n+|(?:\s+-\s+)", cleaned)
        return [part.strip() for part in parts if part.strip()]

    def _looks_like_wrapper_text(self, sentence: str) -> bool:
        wrappers = ["Document ", "source:", "User Query", "用户问题", "Context:", "Structured Data:"]
        if any(wrapper in sentence for wrapper in wrappers):
            return True
        return sentence.startswith("Q:")

    def _extract_sources(self, context: str) -> List[str]:
        sources = re.findall(r"source:\s*([^\n]+)", context, re.I)
        deduped: List[str] = []
        for source in sources:
            source = source.strip(" 。,;；")
            if source and source not in deduped:
                deduped.append(source)
        return deduped[:5]
