from typing import List, Tuple, Optional
from app.rag.vector_store import get_or_create_chroma
from app.rag.embedder import Embedder


class Retriever:
    """RAG 检索器：封装向量检索逻辑。"""

    def __init__(self, merchant_id: str, embedder: Optional[Embedder] = None, top_k: int = 5, persist_root: Optional[str] = None):
        self.merchant_id = merchant_id
        self.embedder = embedder or Embedder()
        self.top_k = top_k
        self.persist_root = persist_root
        self.vector_store = get_or_create_chroma(merchant_id, self.embedder.client, persist_root=self.persist_root)

    def retrieve(self, query: str, k: Optional[int] = None) -> List[Tuple[dict, float]]:
        """执行相似度搜索，返回文档与相似度分数。"""
        if k is None:
            k = self.top_k

        search_results = self.vector_store.similarity_search_with_score(query, k=k)
        results = []
        for document, score in search_results:
            result = {
                "content": document.page_content,
                "metadata": document.metadata,
                "source": document.metadata.get("source", "unknown")
            }
            similarity_score = max(0.0, min(1.0, 1.0 / (1.0 + float(score))))
            results.append((result, similarity_score))
        return results

