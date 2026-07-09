# vector_store.py
import os
import hashlib
import re
from typing import Any, Dict, List, Optional

os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")
from langchain_chroma import Chroma


class VectorStore:
    """向量库包装器：封装 Chroma 实例和检索接口。"""

    def __init__(self, merchant_id: str, embeddings, persist_root: Optional[str] = None):
        self.merchant_id = merchant_id
        self.chroma = get_or_create_chroma(merchant_id, embeddings, persist_root=persist_root)

    def similarity_search_with_score(self, query: str, k: int = 5):
        return self.chroma.similarity_search_with_score(query, k=k)

    def similarity_search_with_product_filter(
        self,
        query: str,
        product_id: str,
        k: int = 5,
        fallback_k: int = 2,
    ) -> List[Any]:
        """按 product_id 过滤后检索，若结果不足则补充全局结果。

        Args:
            query: 搜索关键词
            product_id: 要过滤的商品 ID
            k: 期望的结果数
            fallback_k: 如果过滤结果不足 k，从全局补充多少条

        Returns:
            合并后的 Document 列表（带 score 信息时每项为 (doc, score) 元组）
        """
        # 先用 product_id 过滤
        filter_dict: Dict[str, str] = {"product_id": product_id}
        filtered = self.chroma.similarity_search_with_score(query, k=k, filter=filter_dict)

        # 如果过滤结果达到预期，直接返回
        if len(filtered) >= k:
            return filtered[:k]

        # 不足则从全局补充
        remaining = k - len(filtered)
        global_results = self.chroma.similarity_search_with_score(query, k=fallback_k + remaining)

        # 去重（按 page_content 去重）
        seen = set()
        merged = list(filtered)
        for doc, score in global_results:
            key = doc.page_content[:80]
            if key not in seen:
                seen.add(key)
                merged.append((doc, score))
            if len(merged) >= k:
                break

        return merged[:k]


def normalize_collection_name(merchant_id: str) -> str:
    """Return a deterministic Chroma-safe collection name."""
    raw_name = str(merchant_id or "").strip()
    if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{1,510}[a-zA-Z0-9]", raw_name):
        return raw_name

    digest = hashlib.sha256(raw_name.encode("utf-8")).hexdigest()[:10]
    safe_base = re.sub(r"[^a-zA-Z0-9._-]+", "-", raw_name).strip("._-")
    safe_base = safe_base[:490].rstrip("._-") or "merchant"
    return f"{safe_base}-{digest}"


def get_or_create_chroma(merchant_id: str, embeddings, persist_root: Optional[str] = None) -> Chroma:
	"""
	返回一个以 `merchant_id` 命名并持久化到本地的 Chroma 向量库实例。

	- `embeddings` 应为一个遵循 langchain embeddings 接口的对象（例如 OpenAIEmbeddings）。
	- `persist_root` 可选，默认在项目目录下的 `data/merchants/{merchant_id}/vector_store`。
	"""
	if persist_root is None:
		persist_root = os.path.join(os.getcwd(), "data", "merchants", merchant_id, "vector_store")

	os.makedirs(persist_root, exist_ok=True)
	persist_directory = persist_root

	# 使用 LangChain 的 Chroma wrapper，collection_name 使用 merchant_id
	collection_name = normalize_collection_name(merchant_id)
	chroma = Chroma(persist_directory=persist_directory, collection_name=collection_name, embedding_function=embeddings)
	return chroma

