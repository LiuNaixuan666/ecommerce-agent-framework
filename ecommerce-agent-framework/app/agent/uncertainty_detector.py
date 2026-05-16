# uncertainty_detector.py
"""
不确定性检测模块：实现"守门员"机制

对应论文 Section 3.1 第四阶段：不确定性守门员
该模块通过置信度阈值判定是否触发澄清流程或允许生成回答。
"""

import logging
from typing import Dict, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class UncertaintyResult:
    """不确定性检测结果"""
    is_uncertain: bool                    # 是否不确定（True 则触发澄清）
    confidence_score: float               # 总体置信度 (0.0-1.0)
    retrieval_confidence: float           # 检索置信度
    query_ambiguity_score: float          # 查询歧义度
    recommendation: str                   # 建议行动


class UncertaintyDetector:
    """
    不确定性检测器（Uncertainty Gatekeeper）
    
    核心逻辑：
    - 如果检索到的文档片段置信度过低 → 不带有说服力的回答
    - 如果用户查询本身存在歧义 → 需要澄清
    - 综合这两个信号决定是否允许 LLM 生成回答，或触发澄清流程
    """
    
    # 参数配置（可在实验中微调）
    RETRIEVAL_CONFIDENCE_THRESHOLD = 0.3   # 检索分数阈值
    QUERY_AMBIGUITY_THRESHOLD = 0.6        # 查询歧义阈值
    OVERALL_CONFIDENCE_THRESHOLD = 0.4     # 综合置信度阈值
    
    @staticmethod
    def detect(
        retrieval_scores: list,
        retrieved_documents: list,
        user_query: str,
        intent_confidence: float = 1.0,
        llm_confidence: float = 1.0
    ) -> UncertaintyResult:
        """
        综合检测不确定性。
        
        Args:
            retrieval_scores: Chroma 返回的相似度分数列表 (0～1)
            retrieved_documents: 实际检索到的文档片段
            user_query: 原始用户查询
            intent_confidence: 意图解析的置信度
            
        Returns:
            UncertaintyResult：包含是否应拦截、置信度等信息
        """
        
        # 1. 计算检索置信度
        if not retrieval_scores or len(retrieval_scores) == 0:
            retrieval_confidence = 0.0
            reason_retrieval = "No documents retrieved"
        else:
            top_score = max(retrieval_scores)
            retrieval_confidence = top_score  # 取最高相似度
            reason_retrieval = f"Top retrieval score: {top_score:.3f}"
        
        # 2. 计算查询歧义度（启发式）
        query_ambiguity_score = UncertaintyDetector._compute_query_ambiguity(user_query)
        
        # 3. 综合计算总体置信度
        # 公式：总体置信度 = 检索置信度 × (1 - 歧义度) × 意图置信度 × LLM 自评置信度
        overall_confidence = (
            retrieval_confidence *
            (1.0 - query_ambiguity_score) *
            intent_confidence *
            llm_confidence
        )
        
        # 4. 判定是否不确定
        is_uncertain = overall_confidence < UncertaintyDetector.OVERALL_CONFIDENCE_THRESHOLD
        
        # 5. 生成建议
        if is_uncertain:
            if retrieval_confidence < UncertaintyDetector.RETRIEVAL_CONFIDENCE_THRESHOLD:
                recommendation = "LOW_RETRIEVAL: Trigger clarification flow. Ask user for more specific info."
            elif query_ambiguity_score > UncertaintyDetector.QUERY_AMBIGUITY_THRESHOLD:
                recommendation = "AMBIGUOUS_QUERY: Trigger clarification flow. Ask which option user means."
            else:
                recommendation = "UNCERTAIN: Generate cautious response with disclaimer."
        else:
            recommendation = "CONFIDENT: Generate response normally"
        
        logger.info(
            f"Uncertainty detection: overall_conf={overall_confidence:.3f}, "
            f"retrieval={retrieval_confidence:.3f}, "
            f"ambiguity={query_ambiguity_score:.3f}, "
            f"is_uncertain={is_uncertain}"
        )
        
        return UncertaintyResult(
            is_uncertain=is_uncertain,
            confidence_score=overall_confidence,
            retrieval_confidence=retrieval_confidence,
            query_ambiguity_score=query_ambiguity_score,
            recommendation=recommendation
        )
    
    @staticmethod
    def _compute_query_ambiguity(query: str) -> float:
        """
        计算查询的歧义度。
        
        启发式特征：
        - 查询过短 → 可能歧义
        - 含有多个 OR / 或 → 歧义
        - 实体缺失（如缺少书名、作者） → 歧义
        
        Args:
            query: 用户查询
            
        Returns:
            歧义度 (0.0-1.0)，越高越歧义
        """
        ambiguity = 0.0
        
        # 特征 1：查询长度过短
        if len(query) < 5:
            ambiguity += 0.3
        
        # 特征 2：包含多选词
        or_keywords = ["或", "or", "要么", "还是"]
        or_count = sum(1 for kw in or_keywords if kw in query.lower())
        if or_count > 0:
            ambiguity += min(0.4 * or_count, 0.4)
        
        # 特征 3：问句但缺少核心实体（启发式）
        if "?" in query or "？" in query:
            missing_entity = True
            entity_keywords = ["书", "作者", "价格", "发货", "退货"]
            for keyword in entity_keywords:
                if keyword in query:
                    missing_entity = False
                    break
            if missing_entity:
                ambiguity += 0.2
        
        # 归一化到 [0, 1]
        return min(ambiguity, 1.0)
    
    @staticmethod
    def should_trigger_clarification(uncertainty_result: UncertaintyResult) -> bool:
        """
        判定是否应触发澄清流程。
        
        Args:
            uncertainty_result: 不确定性检测结果
            
        Returns:
            True 表示应触发澄清；False 表示可直接生成回答
        """
        return (
            uncertainty_result.is_uncertain and
            "clarification" in uncertainty_result.recommendation.lower()
        )


def build_clarification_prompt(
    user_query: str,
    uncertainty_reason: str,
    possible_intents: list = None
) -> str:
    """
    构造澄清提示词。
    
    Args:
        user_query: 原始查询
        uncertainty_reason: 不确定的原因
        possible_intents: 可能的意图列表
        
    Returns:
        澄清提示字符串
    """
    if uncertainty_reason == "LOW_RETRIEVAL":
        return (
            f"我理解您问的是: \"{user_query}\"。\n"
            f"但是我在我们的数据库中没有找到很有把握的答案。\n"
            f"能否提供更多细节，比如书名、作者或其他相关信息？"
        )
    elif uncertainty_reason == "AMBIGUOUS_QUERY":
        prompt = f"您的问题: \"{user_query}\" 对我来说有多种理解方式。\n"
        if possible_intents:
            prompt += "您是指：\n"
            for i, intent in enumerate(possible_intents, 1):
                prompt += f"{i}. {intent}\n"
            prompt += "请告诉我您要选择哪一项。"
        return prompt
    else:
        return (
            f"您问: \"{user_query}\"。\n"
            f"我的理解可能不够准确，能否提供更多背景信息？"
        )
