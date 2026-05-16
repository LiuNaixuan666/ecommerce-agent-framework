from app.agent.uncertainty_detector import UncertaintyDetector


def test_llm_confidence_changes_uncertainty():
    retrieval_scores = [0.8]
    retrieved_documents = [{"content": "doc", "metadata": {}, "source": "test"}]
    user_query = "请问这本书的发货时间是多少？"
    intent_confidence = 1.0

    # 高自评置信度 -> 应认为有把握
    res_high = UncertaintyDetector.detect(
        retrieval_scores=retrieval_scores,
        retrieved_documents=retrieved_documents,
        user_query=user_query,
        intent_confidence=intent_confidence,
        llm_confidence=0.95,
    )

    assert res_high.is_uncertain is False

    # 低自评置信度 -> 认为不确定
    res_low = UncertaintyDetector.detect(
        retrieval_scores=retrieval_scores,
        retrieved_documents=retrieved_documents,
        user_query=user_query,
        intent_confidence=intent_confidence,
        llm_confidence=0.2,
    )

    assert res_low.is_uncertain is True
