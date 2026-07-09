from typing import Any, Dict, List, Optional, Tuple

from app.rag.embedder import Embedder
from app.rag.vector_store import get_or_create_chroma


class Retriever:
    """RAG retriever with optional product/platform/shop metadata scopes."""

    def __init__(
        self,
        merchant_id: str,
        embedder: Optional[Embedder] = None,
        top_k: int = 5,
        persist_root: Optional[str] = None,
    ):
        self.merchant_id = merchant_id
        self.embedder = embedder or Embedder()
        self.top_k = top_k
        self.persist_root = persist_root
        self.vector_store = get_or_create_chroma(
            merchant_id,
            self.embedder.client,
            persist_root=self.persist_root,
        )

    def retrieve(
        self,
        query: str,
        k: Optional[int] = None,
        product_id: Optional[str] = None,
        platform: Optional[str] = None,
        shop_id: Optional[str] = None,
    ) -> List[Tuple[dict, float]]:
        if k is None:
            k = self.top_k

        primary_filter = self._metadata_filter(
            product_id=product_id,
            platform=platform,
            shop_id=shop_id,
        )
        if primary_filter:
            search_results = self.vector_store.similarity_search_with_score(
                query,
                k=k,
                filter=primary_filter,
            )
            if len(search_results) < k:
                fallback_filter = self._fallback_filter(
                    product_id=product_id,
                    platform=platform,
                    shop_id=shop_id,
                )
                fallback_results = self._search_with_optional_filter(
                    query=query,
                    k=(k - len(search_results)) + 2,
                    filter_dict=fallback_filter,
                )
                search_results = self._merge_results(search_results, fallback_results, k)
        else:
            search_results = self.vector_store.similarity_search_with_score(query, k=k)

        results = []
        for document, score in search_results:
            result = {
                "content": document.page_content,
                "metadata": document.metadata,
                "source": document.metadata.get("source", "unknown"),
            }
            similarity_score = max(0.0, min(1.0, 1.0 / (1.0 + float(score))))
            results.append((result, similarity_score))
        return results

    def _search_with_optional_filter(
        self,
        query: str,
        k: int,
        filter_dict: Optional[Dict[str, Any]],
    ):
        if filter_dict:
            return self.vector_store.similarity_search_with_score(query, k=k, filter=filter_dict)
        return self.vector_store.similarity_search_with_score(query, k=k)

    def _fallback_filter(
        self,
        product_id: Optional[str],
        platform: Optional[str],
        shop_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        # Product-scoped answers can fall back to platform/shop docs, but platform-
        # scoped answers should not fall back across platforms.
        if product_id and (platform or shop_id):
            return self._metadata_filter(product_id=None, platform=platform, shop_id=shop_id)
        if product_id and not (platform or shop_id):
            return None
        return self._metadata_filter(product_id=product_id, platform=platform, shop_id=shop_id)

    def _metadata_filter(
        self,
        product_id: Optional[str] = None,
        platform: Optional[str] = None,
        shop_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        clauses: List[Dict[str, str]] = []
        if product_id:
            clauses.append({"product_id": product_id})
        if platform:
            clauses.append({"platform": platform})
        if shop_id:
            clauses.append({"shop_id": shop_id})
        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    def _merge_results(self, primary, fallback, k: int):
        seen = {doc.page_content[:80] for doc, _ in primary}
        merged = list(primary)
        for doc, score in fallback:
            key = doc.page_content[:80]
            if key not in seen:
                seen.add(key)
                merged.append((doc, score))
            if len(merged) >= k:
                break
        return merged[:k]
