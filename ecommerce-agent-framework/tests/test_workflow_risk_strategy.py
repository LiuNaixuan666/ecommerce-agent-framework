import os
import asyncio

import pytest

os.environ["DEBUG"] = "false"

from app.agent.workflow import CustomerServiceWorkflow, RetrievalBundle


def structured_retrieval() -> RetrievalBundle:
    return RetrievalBundle(
        structured_data={
            "product_name": "Browser Test Product",
            "sku": "SKU-001",
            "inventory": {"quantity": 12, "status": "in_stock"},
        },
        retrieval_type="structured",
    )


async def fake_retrieve(*args, **kwargs):
    return structured_retrieval()


@pytest.mark.parametrize(
    "query",
    [
        "Can I return this item after opening it?",
        "Can I get a refund for this item?",
        "I need to exchange this product.",
    ],
)
def test_english_return_refund_exchange_are_medium_risk_and_not_auto_sent(query, monkeypatch):
    workflow = CustomerServiceWorkflow()
    monkeypatch.setattr(workflow, "retrieve", fake_retrieve)

    result = asyncio.run(
        workflow.run(
            merchant_id="risk-test",
            user_query=query,
            page_context={"product_name": "Browser Test Product", "sku": "SKU-001", "stock": 12},
        )
    )

    assert result.risk_level == "medium"
    assert result.auto_send_allowed is False
    assert "risk_medium" in result.auto_send_blockers
    assert "问题涉及订单、退款、发票、物流或售后处理" in (result.handoff_reason or "")


@pytest.mark.parametrize(
    "query",
    [
        "I want to complain and demand compensation.",
        "This is fake and I will leave a bad review.",
        "I will report you for fraud.",
    ],
)
def test_english_complaint_compensation_fraud_are_high_risk(query, monkeypatch):
    workflow = CustomerServiceWorkflow()
    monkeypatch.setattr(workflow, "retrieve", fake_retrieve)

    result = asyncio.run(
        workflow.run(
            merchant_id="risk-test",
            user_query=query,
            page_context={"product_name": "Browser Test Product", "sku": "SKU-001", "stock": 12},
        )
    )

    assert result.risk_level == "high"
    assert result.auto_send_allowed is False
    assert result.requires_human_review is True
    assert "risk_high" in result.auto_send_blockers
    assert "human_review_required" in result.auto_send_blockers


# ---------------------------------------------------------------------------
# Integration: product_id matching → RAG filter passing
# ---------------------------------------------------------------------------


def test_workflow_matches_product_and_passes_product_id_to_retriever(monkeypatch, tmp_path):
    """Verify that when page_context contains a product name matching
    a ProductStore record, the retrieve() call receives product_id."""
    from app.storage.product_store import ProductStore
    from app.rag.retriever import Retriever
    import app.agent.workflow as wf

    # Create an isolated store and inject it into the workflow module
    store = ProductStore(str(tmp_path / "products.json"))
    product = store.create({
        "merchant_id": "default",
        "platform": "pinduoduo",
        "title": "儿童科普图书套装",
        "sku": "BOOK-001",
        "price": 59.9,
        "stock": 28,
    })
    monkeypatch.setattr(wf, "product_store", store)

    captured_kwargs = {}

    def _fake_retrieve(self, query, k=None, product_id=None, platform=None, shop_id=None):
        captured_kwargs["product_id"] = product_id
        captured_kwargs["platform"] = platform
        captured_kwargs["shop_id"] = shop_id
        return []

    monkeypatch.setattr(Retriever, "retrieve", _fake_retrieve)

    workflow = CustomerServiceWorkflow()
    result = asyncio.run(
        workflow.run(
            merchant_id="default",
            user_query="这款有现货吗？",
            page_context={
                "platform": "pinduoduo",
                "product_name": "儿童科普图书套装",
                "sku": "BOOK-001",
                "price": 59.9,
                "stock": 28,
            },
        )
    )

    # verify the retriever was called with the matched product_id
    assert captured_kwargs.get("product_id") == product["id"], (
        f"Expected product_id={product['id']}, got {captured_kwargs.get('product_id')}"
    )
    assert captured_kwargs.get("platform") == "pinduoduo"
    # debug metadata should also contain rag_product_filter
    assert result.debug.get("rag_product_filter") == product["id"]


def test_workflow_no_product_match_does_not_filter_rag(monkeypatch, tmp_path):
    """Without a matching page_context, retrieve() should receive product_id=None."""
    from app.storage.product_store import ProductStore
    from app.rag.retriever import Retriever
    import app.agent.workflow as wf

    store = ProductStore(str(tmp_path / "products2.json"))
    monkeypatch.setattr(wf, "product_store", store)

    captured_kwargs = {}

    def _fake_retrieve(self, query, k=None, product_id=None, platform=None, shop_id=None):
        captured_kwargs["product_id"] = product_id
        captured_kwargs["platform"] = platform
        captured_kwargs["shop_id"] = shop_id
        return []

    monkeypatch.setattr(Retriever, "retrieve", _fake_retrieve)

    workflow = CustomerServiceWorkflow()
    asyncio.run(
        workflow.run(
            merchant_id="default",
            user_query="你好",
            page_context=None,
        )
    )

    assert captured_kwargs.get("product_id") is None


def test_normalize_text_whitespace_and_case():
    """_normalize_text helper used in find_by_context."""
    from app.storage.product_store import _normalize_text
    assert _normalize_text("  Hello World  ") == "helloworld"
    assert _normalize_text("立式 全身镜") == "立式全身镜"
    assert _normalize_text(None) == ""
    assert _normalize_text("") == ""
