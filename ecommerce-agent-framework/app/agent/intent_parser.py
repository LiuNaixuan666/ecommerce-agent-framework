from typing import List
import json
import re

from pydantic import BaseModel, Field

from app.llm.factory import get_llm
from app.llm.openai_client import OpenAIClient


class IntentSchema(BaseModel):
    intent_label: str = Field(
        description="One of: PRODUCT_INQUIRY, POLICY_INQUIRY, ORDER_SERVICE, CHITCHAT, OTHERS"
    )
    detected_entities: List[str] = Field(description="Product names, SKUs, order IDs, or other entities mentioned.")
    confidence_score: float = Field(description="Confidence from 0.0 to 1.0")
    reasoning: str = Field(description="Brief reason for this classification")


class IntentParser:
    """Intent parser for general ecommerce customer-service questions.

    The rules intentionally stay broad and domain-neutral. Product-specific
    knowledge should come from merchant data and RAG, not from hardcoded demos.
    """

    def __init__(self, llm=None):
        self.llm = llm or get_llm()

    def _extract_entities(self, user_query: str) -> List[str]:
        entities: List[str] = []

        quoted = re.findall(r"[《\"“]([^》\"”]{1,80})[》\"”]", user_query)
        entities.extend(quoted)

        sku_like = re.findall(r"\b[A-Z0-9][A-Z0-9_-]{2,}\b", user_query, re.I)
        entities.extend(sku_like)

        order_like = re.findall(r"\b(?:ORDER)?\d{6,20}\b", user_query, re.I)
        entities.extend(order_like)

        deduped: List[str] = []
        for entity in entities:
            entity = entity.strip()
            if entity and entity not in deduped:
                deduped.append(entity)
        return deduped

    def _parse_with_rules(self, user_query: str, confidence: float = 0.82) -> IntentSchema:
        query_lower = user_query.lower()
        entities = self._extract_entities(user_query)

        product_keywords = [
            "产品", "商品", "介绍", "详情", "卖点", "特点", "规格", "参数", "材质",
            "尺码", "尺寸", "颜色", "型号", "sku", "价格", "多少钱", "费用", "库存",
            "有货", "现货", "推荐", "适合", "适用", "怎么选", "区别", "对比",
            "product", "price", "stock", "inventory", "sku", "recommend",
        ]
        policy_keywords = [
            "退货", "退款", "换货", "售后", "政策", "规则", "运费", "邮费", "包邮",
            "保修", "质保", "发票", "return", "refund", "policy", "shipping",
            "warranty", "invoice", "exchange", "after-sale", "after sales", "afterservice",
        ]
        order_keywords = [
            "订单", "物流", "发货", "快递", "到哪", "单号", "追踪", "改地址",
            "催发货", "什么时候到", "order", "tracking", "delivery", "address",
        ]
        chitchat_keywords = ["你好", "您好", "哈喽", "hello", "hi", "谢谢", "在吗"]

        def contains_any(keywords: List[str]) -> bool:
            return any(keyword in user_query or keyword in query_lower for keyword in keywords)

        if contains_any(order_keywords):
            intent = "ORDER_SERVICE"
        elif contains_any(policy_keywords):
            intent = "POLICY_INQUIRY"
        elif contains_any(product_keywords):
            intent = "PRODUCT_INQUIRY"
        elif contains_any(chitchat_keywords):
            intent = "CHITCHAT"
            confidence = 0.7
        else:
            intent = "OTHERS"
            confidence = 0.45

        return IntentSchema(
            intent_label=intent,
            detected_entities=entities,
            confidence_score=confidence,
            reasoning="Rule-based ecommerce intent detection",
        )

    def parse(self, user_query: str) -> IntentSchema:
        rule_result = self._parse_with_rules(user_query)
        if rule_result.confidence_score >= 0.8:
            return rule_result

        system_prompt = """
You are a high-precision intent classifier for a general ecommerce customer-service system.
Classify the user query into exactly one label:

1. PRODUCT_INQUIRY: product details, price, stock, SKU, size, recommendation, comparison, usage, suitability.
2. POLICY_INQUIRY: shipping fee, return, refund, exchange, warranty, invoice, store/platform policy.
3. ORDER_SERVICE: order status, delivery, tracking number, address change, shipment delay.
4. CHITCHAT: greeting or small talk.
5. OTHERS: ambiguous, unsupported, or not enough information.

Return valid JSON only:
{
  "intent_label": "...",
  "detected_entities": ["..."],
  "confidence_score": 0.0,
  "reasoning": "..."
}
"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"User Query: {user_query}"},
        ]

        kwargs = {}
        if isinstance(self.llm, OpenAIClient):
            kwargs["response_format"] = {"type": "json_object"}

        try:
            raw_content = self.llm.chat(messages, **kwargs)
            parsed_data = json.loads(raw_content)
            return IntentSchema(**parsed_data)
        except Exception as exc:
            rule_result.reasoning = f"{rule_result.reasoning}; LLM parsing failed: {exc}"
            return rule_result


if __name__ == "__main__":
    parser = IntentParser()
    result = parser.parse("这款商品现在有现货吗？几天能发货？")
    print(f"Intent: {result.intent_label}")
    print(f"Entities: {result.detected_entities}")
    print(f"Reasoning: {result.reasoning}")
