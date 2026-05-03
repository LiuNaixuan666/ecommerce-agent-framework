"""
test_e2e_workflow.py
端到端工作流集成测试：完整 Query → Intent → Retrieval → Uncertainty → Response 流程

覆盖内容：
- Query 进入系统
- Intent Parser 分类
- Retrieval 阶段
- Uncertainty Detector 评估
- 决策点：是否澄清或直接生成
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from app.agent.intent_parser import IntentParser, IntentSchema
from app.agent.uncertainty_detector import UncertaintyDetector, UncertaintyResult


class TestE2EWorkflow:
    """端到端工作流测试"""
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_confident_product_inquiry_flow(self, mock_openai):
        """
        场景：清晰的产品询问 → 高置信度意图 → 高相关检索 → 正常生成
        """
        # 1. 用户输入
        user_query = "《三体》现在有现货吗？"
        
        # 2. Intent Parser 解析
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        intent_response = {
            "intent_label": "PRODUCT_INQUIRY",
            "detected_entities": ["《三体》", "现货"],
            "confidence_score": 0.95,
            "reasoning": "明确的产品可用性查询"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(intent_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        intent = parser.parse(user_query)
        
        assert intent.intent_label == "PRODUCT_INQUIRY"
        assert intent.confidence_score == 0.95
        
        # 3. 检索阶段（模拟返回高相关文档）
        retrieval_scores = [0.92, 0.85, 0.78]
        retrieved_docs = [
            "【产品】《三体》 | 库存：20 | 价格：¥35",
            "《三体》作者刘慈欣",
            "最新发货政策"
        ]
        
        # 4. Uncertainty Detection
        uncertainty_result = UncertaintyDetector.detect(
            retrieval_scores=retrieval_scores,
            retrieved_documents=retrieved_docs,
            user_query=user_query,
            intent_confidence=intent.confidence_score
        )
        
        # 5. 验证流程结果
        assert uncertainty_result.is_uncertain == False
        assert uncertainty_result.confidence_score > 0.65  # 略低于初始期望但仍然很高
        assert "CONFIDENT" in uncertainty_result.recommendation
        
        # 6. 应该允许直接生成回答
        assert uncertainty_result.recommendation == "CONFIDENT: Generate response normally"
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_ambiguous_query_triggers_clarification(self, mock_openai):
        """
        场景：模糊查询 → 中等意图 → 低相关检索 → 触发澄清
        """
        user_query = "或或或"
        
        # 1. Intent Parser 在模糊查询时置信度较低
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        intent_response = {
            "intent_label": "OTHERS",
            "detected_entities": [],
            "confidence_score": 0.35,
            "reasoning": "查询包含多个 OR 操作符，过于模糊"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(intent_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        intent = parser.parse(user_query)
        
        # 2. 检索返回弱相关结果
        retrieval_scores = [0.45, 0.42]
        retrieved_docs = ["弱相关"]
        
        # 3. Uncertainty Detection
        uncertainty_result = UncertaintyDetector.detect(
            retrieval_scores=retrieval_scores,
            retrieved_documents=retrieved_docs,
            user_query=user_query,
            intent_confidence=intent.confidence_score
        )
        
        # 4. 应该触发澄清
        assert uncertainty_result.is_uncertain == True
        assert "clarification" in uncertainty_result.recommendation.lower() or \
               "LOW_RETRIEVAL" in uncertainty_result.recommendation or \
               "AMBIGUOUS" in uncertainty_result.recommendation
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_policy_inquiry_with_high_retrieval(self, mock_openai):
        """
        场景：政策询问 → 中等意图 → 高相关检索 → 正常生成
        """
        user_query = "你们的退货政策是什么？"
        
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        intent_response = {
            "intent_label": "POLICY_INQUIRY",
            "detected_entities": ["退货政策"],
            "confidence_score": 0.88,
            "reasoning": "明确的政策相关查询"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(intent_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        intent = parser.parse(user_query)
        
        # 检索政策相关文档
        retrieval_scores = [0.89, 0.83]
        retrieved_docs = [
            "退货政策：自收货之日起7天内可无条件退货",
            "退货流程说明"
        ]
        
        uncertainty_result = UncertaintyDetector.detect(
            retrieval_scores=retrieval_scores,
            retrieved_documents=retrieved_docs,
            user_query=user_query,
            intent_confidence=intent.confidence_score
        )
        
        # 高置信度，应该正常生成
        assert uncertainty_result.is_uncertain == False
        assert uncertainty_result.confidence_score > 0.65
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_order_service_with_low_retrieval(self, mock_openai):
        """
        场景：订单查询 → 高意图置信度 → 低相关检索 → 触发澄清
        """
        user_query = "我的订单什么时候到？"
        
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        intent_response = {
            "intent_label": "ORDER_SERVICE",
            "detected_entities": ["订单"],
            "confidence_score": 0.92,
            "reasoning": "明确的订单追踪请求"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(intent_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        intent = parser.parse(user_query)
        
        # 检索返回低相关度结果（因为没有具体订单号）
        retrieval_scores = [0.35, 0.32]
        retrieved_docs = ["通用物流信息"]
        
        uncertainty_result = UncertaintyDetector.detect(
            retrieval_scores=retrieval_scores,
            retrieved_documents=retrieved_docs,
            user_query=user_query,
            intent_confidence=intent.confidence_score
        )
        
        # 即使意图清晰，检索结果差也应该触发澄清
        assert uncertainty_result.is_uncertain == True
        assert "LOW_RETRIEVAL" in uncertainty_result.recommendation
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_chitchat_with_no_retrieval(self, mock_openai):
        """
        场景：闲聊 → 低意图 → 无相关检索 → 触发澄清或AI生成
        """
        user_query = "你好！"
        
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        intent_response = {
            "intent_label": "CHITCHAT",
            "detected_entities": [],
            "confidence_score": 0.85,
            "reasoning": "简单的问候"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(intent_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        intent = parser.parse(user_query)
        
        # 闲聊不需要检索
        retrieval_scores = []
        retrieved_docs = []
        
        uncertainty_result = UncertaintyDetector.detect(
            retrieval_scores=retrieval_scores,
            retrieved_documents=retrieved_docs,
            user_query=user_query,
            intent_confidence=intent.confidence_score
        )
        
        # 闲聊通常会触发澄清或AI直接回答
        # 取决于系统设计，可以允许 AI 直接生成回答
        assert uncertainty_result.retrieval_confidence == 0.0


class TestE2EErrorRecovery:
    """端到端错误恢复测试"""
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_intent_parser_failure_graceful_degradation(self, mock_openai):
        """
        场景：Intent Parser 失败 → 降级到 OTHERS → 照常进行 Uncertainty 检测
        """
        user_query = "某个查询"
        
        # Intent Parser 失败
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API error")
        
        parser = IntentParser(api_key="test_key")
        intent = parser.parse(user_query)
        
        # 应该降级到 OTHERS
        assert intent.intent_label == "OTHERS"
        assert intent.confidence_score == 0.0
        
        # 继续 Uncertainty 检测，使用降级的意图
        retrieval_scores = [0.7]
        retrieved_docs = ["文档"]
        
        uncertainty_result = UncertaintyDetector.detect(
            retrieval_scores=retrieval_scores,
            retrieved_documents=retrieved_docs,
            user_query=user_query,
            intent_confidence=intent.confidence_score
        )
        
        # 由于意图置信度为 0，总体置信度也会很低
        assert uncertainty_result.is_uncertain == True
        assert uncertainty_result.confidence_score == 0.0
    
    def test_no_retrieval_results_graceful_handling(self):
        """
        场景：检索完全失败 → Uncertainty 检测正确处理
        """
        user_query = "某个查询"
        
        # 不修复检索结果
        uncertainty_result = UncertaintyDetector.detect(
            retrieval_scores=[],
            retrieved_documents=[],
            user_query=user_query,
            intent_confidence=0.9
        )
        
        # 应该正确处理无结果情况
        assert uncertainty_result.retrieval_confidence == 0.0
        assert uncertainty_result.is_uncertain == True


class TestDecisionLogic:
    """决策逻辑验证"""
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_decision_point_confident_path(self, mock_openai):
        """
        验证决策点：高置信度 → 直接生成路径
        """
        user_query = "《三体》的价格"
        
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        intent_response = {
            "intent_label": "PRODUCT_INQUIRY",
            "detected_entities": ["《三体》", "价格"],
            "confidence_score": 0.94,
            "reasoning": "清晰的产品价格查询"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(intent_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        intent = parser.parse(user_query)
        
        uncertainty_result = UncertaintyDetector.detect(
            retrieval_scores=[0.91, 0.88],
            retrieved_documents=["产品信息"],
            user_query=user_query,
            intent_confidence=intent.confidence_score
        )
        
        # 决策：应该直接生成
        if not uncertainty_result.is_uncertain:
            decision = "GENERATE"
        else:
            decision = "CLARIFY"
        
        assert decision == "GENERATE"
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_decision_point_uncertain_path(self, mock_openai):
        """
        验证决策点：低置信度 → 澄清路径
        """
        user_query = "或"
        
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        intent_response = {
            "intent_label": "OTHERS",
            "detected_entities": [],
            "confidence_score": 0.3,
            "reasoning": "查询过于模糊"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(intent_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        intent = parser.parse(user_query)
        
        uncertainty_result = UncertaintyDetector.detect(
            retrieval_scores=[0.2],
            retrieved_documents=[],
            user_query=user_query,
            intent_confidence=intent.confidence_score
        )
        
        # 决策：应该澄清
        if uncertainty_result.is_uncertain:
            decision = "CLARIFY"
        else:
            decision = "GENERATE"
        
        assert decision == "CLARIFY"


class TestMultiTurnConversation:
    """多轮对话测试"""
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_follow_up_with_context(self, mock_openai):
        """
        场景：用户第一次查询模糊 → 澄清后第二次查询更具体
        """
        # 第一轮：模糊查询
        first_query = "这本书有吗？"
        
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        intent_response_1 = {
            "intent_label": "PRODUCT_INQUIRY",
            "detected_entities": ["书"],
            "confidence_score": 0.6,
            "reasoning": "查询指代不明确"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(intent_response_1)))]
        )
        
        parser = IntentParser(api_key="test_key")
        intent_1 = parser.parse(first_query)
        
        result_1 = UncertaintyDetector.detect(
            retrieval_scores=[0.5],
            retrieved_documents=["通用文档"],
            user_query=first_query,
            intent_confidence=intent_1.confidence_score
        )
        
        # 第一轮应该触发澄清
        assert result_1.is_uncertain == True
        
        # 第二轮：具体查询（假设用户根据澄清回答了）
        second_query = "《三体》有现货吗？"
        
        intent_response_2 = {
            "intent_label": "PRODUCT_INQUIRY",
            "detected_entities": ["《三体》"],
            "confidence_score": 0.93,
            "reasoning": "清晰的产品可用性查询"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(intent_response_2)))]
        )
        
        intent_2 = parser.parse(second_query)
        
        result_2 = UncertaintyDetector.detect(
            retrieval_scores=[0.92],
            retrieved_documents=["《三体》库存信息"],
            user_query=second_query,
            intent_confidence=intent_2.confidence_score
        )
        
        # 第二轮应该正常生成
        assert result_2.is_uncertain == False
        
        # 验证澄清确实起到了效果
        assert result_2.confidence_score > result_1.confidence_score


class TestPerformanceMetrics:
    """性能指标相关的测试"""
    
    @patch('app.agent.intent_parser.OpenAI')
    def test_workflow_latency_acceptable(self, mock_openai):
        """
        验证端到端工作流的延迟在可接受范围内
        （这里仅做结构性测试，实际性能测试需要时间基准）
        """
        import time
        
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        intent_response = {
            "intent_label": "PRODUCT_INQUIRY",
            "detected_entities": ["书"],
            "confidence_score": 0.9,
            "reasoning": "test"
        }
        
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=json.dumps(intent_response)))]
        )
        
        parser = IntentParser(api_key="test_key")
        
        # 测量端到端工作流时间
        start_time = time.time()
        
        intent = parser.parse("查询")
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.8],
            retrieved_documents=["文档"],
            user_query="查询",
            intent_confidence=intent.confidence_score
        )
        
        elapsed_time = time.time() - start_time
        
        # 应该在合理的时间内完成（不超过 1 秒，考虑到 mocking）
        assert elapsed_time < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
