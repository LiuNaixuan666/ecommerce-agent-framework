# vector_store.py
import os
from typing import Optional
try:
    from langchain_community.vectorstores import Chroma
except ImportError:
    from langchain.vectorstores import Chroma


class VectorStore:
    """向量库包装器：封装 Chroma 实例和检索接口。"""

    def __init__(self, merchant_id: str, embeddings, persist_root: Optional[str] = None):
        self.merchant_id = merchant_id
        self.chroma = get_or_create_chroma(merchant_id, embeddings, persist_root=persist_root)

    def similarity_search_with_score(self, query: str, k: int = 5):
        return self.chroma.similarity_search_with_score(query, k=k)


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
	chroma = Chroma(persist_directory=persist_directory, collection_name=merchant_id, embedding_function=embeddings)
	return chroma

