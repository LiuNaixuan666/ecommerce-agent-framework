import json
import time

import pytest

from app.agent.intent_parser import IntentParser
from app.agent.uncertainty_detector import UncertaintyDetector
from app.agent.workflow import CustomerServiceWorkflow


class FakeLLM:
    def __init__(self, payload=None, error: Exception | None = None):
        self.payload = payload
        self.error = error
        self.calls = 0

    def chat(self, messages, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return json.dumps(self.payload, ensure_ascii=False)


def detect(query, intent, scores, documents=None):
    return UncertaintyDetector.detect(
        retrieval_scores=scores,
        retrieved_documents=documents or [],
        user_query=query,
        intent_confidence=intent.confidence_score,
    )


class TestIntentRetrievalDecisionFlow:
    def test_confident_product_inquiry_flow(self):
        query = "这款商品 SKU-001 现在有库存吗？"
        parser = IntentParser(llm=FakeLLM(error=AssertionError("rules should handle this query")))

        intent = parser.parse(query)
        result = detect(query, intent, [0.92, 0.85], ["库存 20 件"])

        assert intent.intent_label == "PRODUCT_INQUIRY"
        assert result.is_uncertain is False
        assert result.recommendation == "CONFIDENT: Generate response normally"

    def test_ambiguous_query_with_weak_retrieval_is_uncertain(self):
        query = "帮我看看这个"
        llm = FakeLLM(
            {
                "intent_label": "OTHERS",
                "detected_entities": [],
                "confidence_score": 0.35,
                "reasoning": "Request is ambiguous",
            }
        )

        intent = IntentParser(llm=llm).parse(query)
        result = detect(query, intent, [0.35], ["弱相关资料"])

        assert llm.calls == 1
        assert result.is_uncertain is True
        assert result.confidence_score < UncertaintyDetector.OVERALL_CONFIDENCE_THRESHOLD
        assert result.recommendation

    def test_policy_inquiry_with_high_retrieval_is_confident(self):
        query = "你们支持七天无理由退货政策吗？"
        intent = IntentParser(llm=FakeLLM(error=AssertionError("rules should handle policy"))).parse(query)

        result = detect(query, intent, [0.95], ["签收后七天内支持无理由退货"])

        assert intent.intent_label == "POLICY_INQUIRY"
        assert result.is_uncertain is False

    def test_order_service_with_low_retrieval_is_uncertain(self):
        query = "我的订单 123456 什么时候到？"
        intent = IntentParser(llm=FakeLLM(error=AssertionError("rules should handle order"))).parse(query)

        result = detect(query, intent, [0.2], ["通用物流说明"])

        assert intent.intent_label == "ORDER_SERVICE"
        assert result.is_uncertain is True
        assert result.recommendation.startswith("LOW_RETRIEVAL")

    def test_chitchat_can_be_classified_by_injected_llm(self):
        llm = FakeLLM(
            {
                "intent_label": "CHITCHAT",
                "detected_entities": [],
                "confidence_score": 0.85,
                "reasoning": "Greeting",
            }
        )

        intent = IntentParser(llm=llm).parse("你好")

        assert intent.intent_label == "CHITCHAT"
        assert intent.confidence_score == pytest.approx(0.85)
        assert llm.calls == 1


class TestErrorRecovery:
    def test_intent_llm_failure_uses_rule_fallback(self):
        parser = IntentParser(llm=FakeLLM(error=RuntimeError("provider unavailable")))

        result = parser.parse("帮我判断一下")

        assert result.intent_label == "OTHERS"
        assert result.confidence_score == pytest.approx(0.45)
        assert "LLM parsing failed" in result.reasoning

    def test_no_retrieval_results_is_uncertain(self):
        result = UncertaintyDetector.detect(
            retrieval_scores=[],
            retrieved_documents=[],
            user_query="这款商品怎么样？",
            intent_confidence=0.82,
        )

        assert result.retrieval_confidence == 0.0
        assert result.is_uncertain is True
        assert result.recommendation.startswith("LOW_RETRIEVAL")


class TestDecisionLogic:
    def test_confident_result_does_not_trigger_clarification(self):
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.95],
            retrieved_documents=["直接证据"],
            user_query="SKU-001 的价格是多少？",
            intent_confidence=0.9,
        )

        assert result.is_uncertain is False
        assert UncertaintyDetector.should_trigger_clarification(result) is False

    def test_low_retrieval_result_triggers_clarification(self):
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.1],
            retrieved_documents=[],
            user_query="这个怎么样？",
            intent_confidence=0.8,
        )

        assert result.is_uncertain is True
        assert UncertaintyDetector.should_trigger_clarification(result) is True


class TestMultiTurnConversation:
    def test_clarification_choice_includes_previous_user_question(self):
        workflow = CustomerServiceWorkflow()
        history = [
            {"role": "user", "content": "这个什么时候发货？"},
            {"role": "assistant", "content": "请确认咨询类型"},
        ]

        effective_query = workflow._build_effective_query("order", history)

        assert "这个什么时候发货？" in effective_query
        assert "order" in effective_query


class TestPerformance:
    def test_rule_classification_latency(self):
        parser = IntentParser(llm=FakeLLM(error=AssertionError("LLM should not be called")))

        started = time.perf_counter()
        for _ in range(100):
            result = parser.parse("SKU-001 现在有库存吗？")
            assert result.intent_label == "PRODUCT_INQUIRY"
        elapsed = time.perf_counter() - started

        assert elapsed < 1.0
