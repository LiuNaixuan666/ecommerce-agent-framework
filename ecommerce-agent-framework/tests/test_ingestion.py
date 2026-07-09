def test_ingest_merchant_documents(tmp_path, monkeypatch):
    """
    Test ingestion pipeline with mocked Chroma and embeddings (no real API calls).
    """
    # Mock the Chroma vector store
    class MockChroma:
        def __init__(self):
            self.added = []

        def add_texts(self, texts, metadatas=None):
            self.added = list(zip(texts, metadatas or []))
            return None

        def persist(self):
            return None

    # Mock embeddings to avoid real OpenAI API calls
    class MockEmbeddings:
        def embed_documents(self, docs):
            return [[0.0] * 1536] * len(docs)

        def embed_query(self, text):
            return [0.0] * 1536

    # Patch get_or_create_chroma to return our mock
    def mock_get_or_create_chroma(merchant_id, embeddings, persist_root=None):
        return MockChroma()

    # Build a real merchant directory with test files
    merchant_dir = tmp_path / "merchant_test"
    raw = merchant_dir / "raw_docs"
    products = merchant_dir / "products"
    raw.mkdir(parents=True)
    products.mkdir(parents=True)

    # Create small text and csv files
    (raw / "faq.txt").write_text("Q: 本店是否有测试书?\nA: 有。\n", encoding="utf-8")
    (products / "books.csv").write_text(
        "id,title,author,category,description\n1,测试书,作者,分类,简介示例\n",
        encoding="utf-8"
    )

    monkeypatch.setattr(
        "app.knowledge.ingestion.get_or_create_chroma",
        mock_get_or_create_chroma,
    )
    from app.knowledge.ingestion import ingest_merchant_documents

    result = ingest_merchant_documents(
        "merchant_test",
        merchant_dir=str(merchant_dir),
        embeddings=MockEmbeddings(),
    )

    assert isinstance(result, dict)
    assert result.get("status") == "ok"
    assert result.get("documents", 0) >= 1
    assert result.get("chunks", 0) >= 1
