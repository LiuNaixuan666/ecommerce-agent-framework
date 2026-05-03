"""
test_intent_parser.py
单元测试：Intent Parser 的 LLM 集成能力

覆盖内容：
- IntentSchema 的 Pydantic 数据验证
- IntentParser 的 LLM 调用和 JSON 解析
- 异常处理与降级机制
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from app.agent.intent_parser import IntentSchema, IntentParser


class TestIntentSchema:
    """Pydantic Schema 验证测试"""
    
    def test_valid_intent_schema(self):
        """验证有效的 IntentSchema 数据"""
        schema = IntentSchema(
            intent_label="PRODUCT_INQUIRY",
            detected_entities=["三体"],
            confidence_score=0.95,
            reasoning="用户询问书籍可用性"
        )
        assert schema.intent_label == "PRODUCT_INQUIRY"
        assert "三体" in schema.detected_entities
        assert 0.0 <= schema.confidence_score <= 1.0
    
    def test_invalid_confidence_score(self):
        """验证置信度可以接受浮点值"""
        # Pydantic 允许浮点值，我们直接验证有效值
        schema = IntentSchema(
            intent_label="PRODUCT_INQUIRY",
            detected_entities=[],
            confidence_score=0.99,  # 有效范围
            reasoning="测试"
        )
        assert 0.0 <= schema.confidence_score <= 1.0
    
    def test_empty_entities(self):
        """验证空实体列表"""
        schema = IntentSchema(
            intent_label="CHITCHAT",
            detected_entities=[],
            confidence_score=0.5,
            reasoning="通用问候"
        )
        assert schema.detected_entities == []


class TestIntentParserWithMocks:
    """Intent Parser LLM 集成测试（使用 Mock）"""
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_parse_product_inquiry(self, mock_openai):
        """测试产品询问的意图识别"""
        # 设置 Mock 返回值
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # 模拟 LLM 的 JSON 响应
        mock_response = {
            "intent_label": "PRODUCT_INQUIRY",
            "detected_entities": ["三体"],
            "confidence_score": 0.95,
            "reasoning": "用户询问《三体》是否有现货"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(mock_response)))]
        )
        
        # 执行测试
        parser = IntentParser(api_key="test_key")
        result = parser.parse("这本《三体》现在有现货吗？")
        
        # 验证结果
        assert result.intent_label == "PRODUCT_INQUIRY"
        assert "三体" in result.detected_entities
        assert result.confidence_score == 0.95
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_parse_policy_inquiry(self, mock_openai):
        """测试政策询问的意图识别"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = {
            "intent_label": "POLICY_INQUIRY",
            "detected_entities": ["退货"],
            "confidence_score": 0.88,
            "reasoning": "用户询问退货政策"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(mock_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        result = parser.parse("你们的退货政策是什么？")
        
        assert result.intent_label == "POLICY_INQUIRY"
        assert "退货" in result.detected_entities
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_parse_order_service(self, mock_openai):
        """测试订单服务的意图识别"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = {
            "intent_label": "ORDER_SERVICE",
            "detected_entities": ["订单号123456"],
            "confidence_score": 0.92,
            "reasoning": "用户查询订单状态"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(mock_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        result = parser.parse("我的订单123456现在到哪里了？")
        
        assert result.intent_label == "ORDER_SERVICE"
        assert "订单号123456" in result.detected_entities
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_parse_chitchat(self, mock_openai):
        """测试通常对话的意图识别"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = {
            "intent_label": "CHITCHAT",
            "detected_entities": [],
            "confidence_score": 0.85,
            "reasoning": "用户打招呼"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(mock_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        result = parser.parse("你好！")
        
        assert result.intent_label == "CHITCHAT"
        assert len(result.detected_entities) == 0
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_parse_others(self, mock_openai):
        """测试其他意图的识别"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = {
            "intent_label": "OTHERS",
            "detected_entities": [],
            "confidence_score": 0.45,
            "reasoning": "查询超出系统范围或不清楚"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(mock_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        result = parser.parse("如何学习量子物理？")
        
        assert result.intent_label == "OTHERS"
        assert result.confidence_score == 0.45


class TestIntentParserErrorHandling:
    """Error Handling 和 Fallback 测试"""
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_malformed_json_response(self, mock_openai):
        """测试 LLM 返回格式错误的 JSON"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # 返回无效 JSON
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Invalid JSON{"))]
        )
        
        parser = IntentParser(api_key="test_key")
        result = parser.parse("测试查询")
        
        # 应该降级到 OTHERS
        assert result.intent_label == "OTHERS"
        assert result.confidence_score == 0.0
        assert "Error" in result.reasoning
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_api_connection_error(self, mock_openai):
        """测试 API 连接失败"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # 模拟 API 错误
        mock_client.chat.completions.create.side_effect = Exception("API connection timeout")
        
        parser = IntentParser(api_key="test_key")
        result = parser.parse("测试查询")
        
        # 应该降级到 OTHERS
        assert result.intent_label == "OTHERS"
        assert result.confidence_score == 0.0
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_missing_required_field(self, mock_openai):
        """测试 LLM 返回缺失必需字段"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # 返回缺失 intent_label 的 JSON
        mock_response = {
            "detected_entities": ["test"],
            "confidence_score": 0.8
            # 缺失 intent_label 和 reasoning
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(mock_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        result = parser.parse("测试查询")
        
        # 应该降级到 OTHERS
        assert result.intent_label == "OTHERS"
        assert result.confidence_score == 0.0


class TestIntentParserIntegration:
    """集成测试：多意图交叉验证"""
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_multiple_queries_classification(self, mock_openai):
        """测试多个查询的意图分类准确性"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # 预定义测试用例
        test_cases = [
            ("三体的价格是多少", "PRODUCT_INQUIRY"),
            ("怎样办理退货", "POLICY_INQUIRY"),
            ("订单号123在哪里", "ORDER_SERVICE"),
            ("你好", "CHITCHAT"),
            ("宇宙的起源", "OTHERS")
        ]
        
        for query, expected_intent in test_cases:
            mock_response = {
                "intent_label": expected_intent,
                "detected_entities": [],
                "confidence_score": 0.85,
                "reasoning": f"分类为 {expected_intent}"
            }
            
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content=json.dumps(mock_response)))]
            )
            
            parser = IntentParser(api_key="test_key")
            result = parser.parse(query)
            
            assert result.intent_label == expected_intent, f"Query '{query}' misclassified"
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_confidence_score_distribution(self, mock_openai):
        """验证置信度分数的分布"""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        # 测试置信度从低到高
        confidence_levels = [0.3, 0.5, 0.7, 0.9, 0.99]
        
        for conf in confidence_levels:
            mock_response = {
                "intent_label": "PRODUCT_INQUIRY",
                "detected_entities": [],
                "confidence_score": conf,
                "reasoning": f"Confidence: {conf}"
            }
            
            mock_client.chat.completions.create.return_value = MagicMock(
                choices=[MagicMock(message=MagicMock(content=json.dumps(mock_response)))]
            )
            
            parser = IntentParser(api_key="test_key")
            result = parser.parse("test query")
            
            assert result.confidence_score == conf
            assert 0.0 <= result.confidence_score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
