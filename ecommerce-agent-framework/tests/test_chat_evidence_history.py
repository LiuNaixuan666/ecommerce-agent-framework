from types import SimpleNamespace

from app.api.routes_chat import _workflow_message_metadata
from app.models.schemas import ConversationMessage


def test_workflow_message_metadata_keeps_retrieval_evidence():
    result = SimpleNamespace(
        intent="product_info",
        confidence=0.88,
        sources=["catalog"],
        retrieval_type="hybrid",
        evidence_sources=[
            {
                "type": "rag_chunk",
                "source": "catalog",
                "product_id": "product-1",
                "score": 0.91,
                "preview": "Product details",
            }
        ],
        risk_level="low",
        auto_send_allowed=True,
        auto_send_blockers=[],
        requires_human_review=False,
    )

    metadata = _workflow_message_metadata(result, source="rpa", request_id="request-1")

    assert metadata["retrieval_type"] == "hybrid"
    assert metadata["evidence_sources"][0]["product_id"] == "product-1"
    assert metadata["request_id"] == "request-1"


def test_conversation_message_response_preserves_metadata():
    message = ConversationMessage(
        role="assistant",
        content="Recommended answer",
        metadata={
            "retrieval_type": "rag",
            "evidence_sources": [{"type": "rag_chunk", "source": "faq"}],
        },
    )

    payload = message.model_dump()

    assert payload["metadata"]["retrieval_type"] == "rag"
    assert payload["metadata"]["evidence_sources"][0]["source"] == "faq"
