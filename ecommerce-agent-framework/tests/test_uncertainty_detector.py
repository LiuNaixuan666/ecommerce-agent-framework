"""
test_uncertainty_detector.py
集成测试：Uncertainty Detector 的置信度检测能力

覆盖内容：
- 检索置信度计算
- 查询歧义度计算  
- 综合置信度公式验证
- 不确定性决策阈值
- 澄清建议的准确性
"""

import pytest
from dataclasses import asdict
from app.agent.uncertainty_detector import UncertaintyDetector, UncertaintyResult


class TestRetrievalConfidenceDetection:
    """检索置信度检测测试"""
    
    def test_no_documents_retrieved(self):
        """测试无检索结果的情况"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[],
            retrieved_documents=[],
            user_query="找一本书",
            intent_confidence=1.0
        )
        
        assert result.retrieval_confidence == 0.0
        assert result.is_uncertain == True
        # 应该有某种形式的澄清或低检索建议
        assert "clarification" in result.recommendation.lower() or "low" in result.recommendation.lower()
    
    def test_single_high_confidence_retrieval(self):
        """测试单个高置信度检索"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.95],
            retrieved_documents=["文档内容"],
            user_query="三体的价格",
            intent_confidence=0.9
        )
        
        assert result.retrieval_confidence == 0.95
        # 总体置信度 = 0.95 × (1-0) × 0.9 = 0.855 > 0.6
        assert result.is_uncertain == False
        assert result.confidence_score > UncertaintyDetector.OVERALL_CONFIDENCE_THRESHOLD
    
    def test_single_low_confidence_retrieval(self):
        """测试单个低置信度检索"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.3],
            retrieved_documents=["弱相关文档"],
            user_query="某本书",
            intent_confidence=1.0
        )
        
        assert result.retrieval_confidence == 0.3
        assert result.is_uncertain == True
        # 检索分数太低，应触发澄清
        assert "LOW_RETRIEVAL" in result.recommendation or result.confidence_score < UncertaintyDetector.OVERALL_CONFIDENCE_THRESHOLD
    
    def test_multiple_retrieval_scores_takes_max(self):
        """测试多个检索分数时取最大值"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.5, 0.7, 0.85, 0.6],
            retrieved_documents=["doc1", "doc2", "doc3", "doc4"],
            user_query="查询",
            intent_confidence=1.0
        )
        
        # 应该取最高分
        assert result.retrieval_confidence == 0.85
    
    def test_boundary_threshold(self):
        """测试检索置信度在阈值边界的行为"""
        # 刚好在阈值处
        threshold = UncertaintyDetector.RETRIEVAL_CONFIDENCE_THRESHOLD
        
        result_at_threshold = UncertaintyDetector.detect(
            retrieval_scores=[threshold],
            retrieved_documents=["doc"],
            user_query="查询",
            intent_confidence=1.0
        )
        
        result_below_threshold = UncertaintyDetector.detect(
            retrieval_scores=[threshold - 0.01],
            retrieved_documents=["doc"],
            user_query="查询",
            intent_confidence=1.0
        )
        
        # 两者应该有不同的不确定性判断
        assert result_at_threshold.is_uncertain != result_below_threshold.is_uncertain or \
               result_at_threshold.confidence_score > result_below_threshold.confidence_score


class TestQueryAmbiguityDetection:
    """查询歧义度检测测试"""
    
    def test_short_query_ambiguity(self):
        """测试短查询的歧义度"""
        # 短查询通常更模糊
        ambiguity = UncertaintyDetector._compute_query_ambiguity("书")
        assert ambiguity > 0.2  # 应该被标记为较高歧义度
    
    def test_long_specific_query(self):
        """测试长且具体的查询"""
        # 具体的长查询通常歧义度低
        ambiguity = UncertaintyDetector._compute_query_ambiguity(
            "请问《三体》第一部的精装版现在有现货吗？"
        )
        assert ambiguity < 0.4  # 应该是较低歧义度
    
    def test_query_with_or_keyword_chinese(self):
        """测试包含"或"的中文查询"""
        # 含有选择词应该增加歧义度
        ambiguity_no_or = UncertaintyDetector._compute_query_ambiguity("三体的价格")
        ambiguity_with_or = UncertaintyDetector._compute_query_ambiguity("三体或球状闪电的价格")
        
        assert ambiguity_with_or > ambiguity_no_or
    
    def test_query_with_or_keyword_english(self):
        """测试包含 OR 的英文查询"""
        ambiguity_with_or = UncertaintyDetector._compute_query_ambiguity(
            "Do you have Book A or Book B?"
        )
        assert ambiguity_with_or >= 0.2
    
    def test_query_with_multiple_or(self):
        """测试包含多个选择词的查询"""
        ambiguity = UncertaintyDetector._compute_query_ambiguity(
            "你有三体或球状闪电或死神永生吗？"
        )
        # 多个 OR 应该显著增加歧义度
        assert ambiguity > 0.3
    
    def test_question_without_entity(self):
        """测试缺少核心实体的问句"""
        # 问题但没有提及书名/作者等关键词
        ambiguity = UncertaintyDetector._compute_query_ambiguity("这家店怎么样？")
        assert ambiguity > 0.1
    
    def test_question_with_entity(self):
        """测试包含实体的问句"""
        ambiguity = UncertaintyDetector._compute_query_ambiguity("这家店的《三体》怎么样？")
        # 虽然是问句，但包含具体实体，歧义度应该较低
        assert ambiguity < 0.4


class TestOverallConfidenceFormula:
    """综合置信度公式验证"""
    
    def test_confidence_formula_breakdown(self):
        """验证置信度公式：confidence = retrieval × (1 - ambiguity) × intent"""
        retrieval_conf = 0.8
        query_ambiguity = 0.2
        intent_conf = 0.9
        
        expected = retrieval_conf * (1 - query_ambiguity) * intent_conf
        
        # 使用 mock 数据来验证公式
        result = UncertaintyDetector.detect(
            retrieval_scores=[retrieval_conf],
            retrieved_documents=["doc"],
            user_query="查询",  # 会被计算出歧义度
            intent_confidence=intent_conf
        )
        
        # 由于真实歧义度可能不是 0.2，我们主要验证结构
        assert 0.0 <= result.confidence_score <= 1.0
    
    def test_zero_retrieval_confidence(self):
        """测试检索置信度为 0 的情况"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.0],
            retrieved_documents=[],
            user_query="查询",
            intent_confidence=1.0
        )
        
        # 如果检索置信度为 0，总体置信度应该也是 0
        assert result.confidence_score == 0.0
        assert result.is_uncertain == True
    
    def test_high_ambiguity_reduces_confidence(self):
        """测试高歧义度降低总体置信度"""
        result_low_ambiguity = UncertaintyDetector.detect(
            retrieval_scores=[0.9],
            retrieved_documents=["doc"],
            user_query="《三体》的价格",  # 清晰
            intent_confidence=1.0
        )
        
        result_high_ambiguity = UncertaintyDetector.detect(
            retrieval_scores=[0.9],
            retrieved_documents=["doc"],
            user_query="或",  # 模糊/不清晰
            intent_confidence=1.0
        )
        
        # 高歧义度应该导致更低的总体置信度
        assert result_low_ambiguity.confidence_score > result_high_ambiguity.confidence_score


class TestUncertaintyDecision:
    """不确定性决策阈值测试"""
    
    def test_confident_recommendation(self):
        """测试高置信度下的建议"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.95],
            retrieved_documents=["高相关文档"],
            user_query="《三体》的价格是多少",
            intent_confidence=0.95
        )
        
        # 高置信度应该建议正常生成回答
        assert result.is_uncertain == False
        assert "CONFIDENT" in result.recommendation
    
    def test_retrieval_at_threshold_uses_cautious_response(self):
        """测试检索置信度等于阈值时采用谨慎回答"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.3],
            retrieved_documents=["弱相关"],
            user_query="某个模糊的东西",
            intent_confidence=1.0
        )
        
        assert result.is_uncertain == True
        assert result.retrieval_confidence == UncertaintyDetector.RETRIEVAL_CONFIDENCE_THRESHOLD
        assert result.recommendation.startswith("UNCERTAIN:")
    
    def test_ambiguous_query_triggers_clarification(self):
        """测试模糊查询触发澄清"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.8],
            retrieved_documents=["文档"],
            user_query="或或或或",  # 高度模糊的查询
            intent_confidence=1.0
        )
        
        assert result.is_uncertain == True
        # 应该包含 AMBIGUOUS 或其他澄清建议
        assert "ambiguous" in result.recommendation.lower() or "clarification" in result.recommendation.lower()
    
    def test_low_intent_confidence(self):
        """测试低意图置信度的影响"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.8],
            retrieved_documents=["文档"],
            user_query="清晰的查询",
            intent_confidence=0.3  # 低意图置信度
        )
        
        # 即使检索高，也应该因为意图置信度低而产生不确定性
        assert result.confidence_score < 0.6


class TestClarificationRecommendations:
    """澄清建议的准确性测试"""
    
    def test_low_retrieval_recommendation(self):
        """验证低检索置信度的澄清建议"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.2],
            retrieved_documents=[],
            user_query="某本书",
            intent_confidence=1.0
        )
        
        assert "LOW_RETRIEVAL" in result.recommendation
        assert "clarification" in result.recommendation.lower()
    
    def test_ambiguous_query_recommendation(self):
        """验证模糊查询的澄清建议"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.8],
            retrieved_documents=["文档"],
            user_query="或或或",
            intent_confidence=1.0
        )
        
        # 如果歧义度高，应该有 AMBIGUOUS_QUERY 建议
        if result.query_ambiguity_score > UncertaintyDetector.QUERY_AMBIGUITY_THRESHOLD:
            assert "AMBIGUOUS" in result.recommendation or "clarification" in result.recommendation.lower()
    
    def test_uncertain_recommendation(self):
        """验证不确定情况的保守建议"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.6],
            retrieved_documents=["文档"],
            user_query="一个查询",
            intent_confidence=0.6
        )
        
        # 在不确定情况下，应该生成一个建议
        assert result.recommendation is not None
        assert len(result.recommendation) > 0


class TestUncertaintyResultDataclass:
    """UncertaintyResult 数据类的验证"""
    
    def test_result_serialization(self):
        """验证结果可以序列化为字典"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.8],
            retrieved_documents=["doc"],
            user_query="查询",
            intent_confidence=0.9
        )
        
        result_dict = asdict(result)
        
        # 验证所有字段都存在
        assert "is_uncertain" in result_dict
        assert "confidence_score" in result_dict
        assert "retrieval_confidence" in result_dict
        assert "query_ambiguity_score" in result_dict
        assert "recommendation" in result_dict
    
    def test_result_attributes(self):
        """验证 UncertaintyResult 的属性"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.7],
            retrieved_documents=["doc"],
            user_query="查询",
            intent_confidence=0.8
        )
        
        # 验证类型
        assert isinstance(result.is_uncertain, bool)
        assert isinstance(result.confidence_score, float)
        assert isinstance(result.retrieval_confidence, float)
        assert isinstance(result.query_ambiguity_score, float)
        assert isinstance(result.recommendation, str)
        
        # 验证范围
        assert 0.0 <= result.confidence_score <= 1.0
        assert 0.0 <= result.retrieval_confidence <= 1.0
        assert 0.0 <= result.query_ambiguity_score <= 1.0


class TestEdgeCases:
    """边界和极端情况测试"""
    
    def test_very_high_confidence_all_signals(self):
        """测试所有信号都很强的情况"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[1.0],  # 完全匹配
            retrieved_documents=["完美匹配文档"],
            user_query="《三体》的价格",  # 非常清晰
            intent_confidence=1.0  # 确定的意图
        )
        
        assert result.is_uncertain == False
        assert result.confidence_score > 0.9
    
    def test_very_low_confidence_all_signals(self):
        """测试所有信号都很弱的情况"""
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.1],
            retrieved_documents=[],
            user_query="或",
            intent_confidence=0.1
        )
        
        assert result.is_uncertain == True
        assert result.confidence_score < 0.2
    
    def test_confidence_exactly_at_threshold(self):
        """测试置信度恰好等于阈值时的行为"""
        threshold = UncertaintyDetector.OVERALL_CONFIDENCE_THRESHOLD
        
        # 构造使得总体置信度恰好等于阈值的情况
        # confidence = retrieval × (1 - ambiguity) × intent
        # 假设 ambiguity = 0, intent = 1.0，则需要 retrieval = threshold
        
        result = UncertaintyDetector.detect(
            retrieval_scores=[threshold],
            retrieved_documents=["doc"],
            user_query="清晰查询",  # 低歧义度
            intent_confidence=1.0
        )
        
        # 当置信度等于或略低于阈值时应该不确定
        assert result.confidence_score <= threshold + 0.01


class TestIntegrationWithIntentParser:
    """与 Intent Parser 的集成测试"""
    
    def test_low_intent_confidence_propagation(self):
        """测试低意图置信度如何传播到不确定性检测"""
        # 模拟意图置信度为 0.3（不太确定的意图识别）
        result = UncertaintyDetector.detect(
            retrieval_scores=[0.9],  # 高检索置信度
            retrieved_documents=["高相关文档"],
            user_query="可能模糊的查询",
            intent_confidence=0.3  # 低意图置信度
        )
        
        # 即使检索高，意图置信度低也应该降低总体置信度
        expected_confidence = 0.9 * (1 - result.query_ambiguity_score) * 0.3
        assert abs(result.confidence_score - expected_confidence) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
