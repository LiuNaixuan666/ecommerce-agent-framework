from typing import List
from app.embeddings.factory import get_embedding_client


class Embedder:
    """统一向量化接口，封装 embeddings provider。"""

    def __init__(self, client=None):
        self.client = client or get_embedding_client()

    def embed_documents(self, texts: List[str]):
        """将文本列表转换为向量列表。"""
        return self.client.embed_documents(texts)

    def embed_query(self, text: str):
        """将查询文本转换为向量。"""
        return self.client.embed_query(text)

