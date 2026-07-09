import json

import pytest

from app.agent.intent_parser import IntentParser, IntentSchema


class FakeLLM:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls = []

    def chat(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        if self.error:
            raise self.error
        if isinstance(self.response, str):
            return self.response
        return json.dumps(self.response, ensure_ascii=False)


class TestIntentSchema:
    def test_valid_intent_schema(self):
        schema = IntentSchema(
            intent_label="PRODUCT_INQUIRY",
            detected_entities=["三体"],
            confidence_score=0.95,
            reasoning="用户询问商品库存",
        )

        assert schema.intent_label == "PRODUCT_INQUIRY"
        assert schema.detected_entities == ["三体"]
        assert 0.0 <= schema.confidence_score <= 1.0

    def test_empty_entities(self):
        schema = IntentSchema(
            intent_label="CHITCHAT",
            detected_entities=[],
            confidence_score=0.7,
            reasoning="用户问候",
        )

        assert schema.detected_entities == []


class TestRuleFirstBehavior:
    @pytest.mark.parametrize(
        ("query", "expected_intent"),
        [
            ("What is the price of SKU-123?", "PRODUCT_INQUIRY"),
            ("Can I get a refund?", "POLICY_INQUIRY"),
            ("Where is order 123456?", "ORDER_SERVICE"),
        ],
    )
    def test_high_confidence_rules_do_not_call_llm(self, query, expected_intent):
        llm = FakeLLM(error=AssertionError("LLM should not be called"))
        parser = IntentParser(llm=llm)

        result = parser.parse(query)

        assert result.intent_label == expected_intent
        assert result.confidence_score == pytest.approx(0.82)
        assert llm.calls == []

    def test_extracts_quoted_sku_and_order_entities(self):
        parser = IntentParser(llm=FakeLLM())

        entities = parser._extract_entities('请查询《三体》、SKU-123 和 ORDER123456')

        assert "三体" in entities
        assert "SKU-123" in entities
        assert "ORDER123456" in entities


class TestLLMClassification:
    @pytest.mark.parametrize(
        ("intent", "entities", "confidence"),
        [
            ("PRODUCT_INQUIRY", ["商品A"], 0.95),
            ("POLICY_INQUIRY", ["退货"], 0.88),
            ("ORDER_SERVICE", ["ORDER123456"], 0.92),
            ("CHITCHAT", [], 0.85),
            ("OTHERS", [], 0.45),
        ],
    )
    def test_low_confidence_rule_result_uses_injected_llm(self, intent, entities, confidence):
        llm = FakeLLM(
            {
                "intent_label": intent,
                "detected_entities": entities,
                "confidence_score": confidence,
                "reasoning": "Fake LLM classification",
            }
        )
        parser = IntentParser(llm=llm)

        result = parser.parse("请帮我判断一下这个请求")

        assert result.intent_label == intent
        assert result.detected_entities == entities
        assert result.confidence_score == pytest.approx(confidence)
        assert len(llm.calls) == 1
        assert "intent_label" in llm.calls[0]["messages"][0]["content"]

    def test_generic_llm_receives_provider_neutral_arguments(self):
        llm = FakeLLM(
            {
                "intent_label": "OTHERS",
                "detected_entities": [],
                "confidence_score": 0.5,
                "reasoning": "Unknown request",
            }
        )

        IntentParser(llm=llm).parse("请帮我判断一下")

        assert llm.calls[0]["kwargs"] == {}


class TestIntentParserFallback:
    @pytest.mark.parametrize(
        "llm",
        [
            FakeLLM("Invalid JSON{"),
            FakeLLM(
                {
                    "detected_entities": ["test"],
                    "confidence_score": 0.8,
                }
            ),
            FakeLLM(error=RuntimeError("API connection timeout")),
        ],
    )
    def test_invalid_llm_result_falls_back_to_rule_result(self, llm):
        parser = IntentParser(llm=llm)

        result = parser.parse("请帮我判断一下这个请求")

        assert result.intent_label == "OTHERS"
        assert result.confidence_score == pytest.approx(0.45)
        assert "LLM parsing failed" in result.reasoning
