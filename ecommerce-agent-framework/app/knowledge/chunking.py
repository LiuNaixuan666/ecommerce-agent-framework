# chunking.py
from typing import List, Dict, Optional
from langchain.text_splitter import RecursiveCharacterTextSplitter


def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
	"""
	将单个长文本切分为多个片段。
	"""
	splitter = RecursiveCharacterTextSplitter(
		chunk_size=chunk_size,
		chunk_overlap=chunk_overlap,
		separators=["\n\n", "\n", " ", ""]
	)
	return splitter.split_text(text)


def split_documents(
    documents: List[Dict],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    product_id: Optional[str] = None,
    platform: Optional[str] = None,
    shop_id: Optional[str] = None,
) -> List[Dict]:
    """
    接收 parse 后的文档列表，返回切分后的片段列表。

    输入 documents 格式: [{"source": "filename", "content": "..."}, ...]
    返回格式: [{"text": "chunk_text", "metadata": {"source": filename, "chunk_index": i}}, ...]

    如果指定 product_id，所有 chunk 的 metadata 中会写入 product_id 字段，
    用于后续按商品过滤的向量检索。
    """
    chunks = []
    for doc in documents:
        source = doc.get("source", "unknown")
        content = doc.get("content", "")
        if not content:
            continue

        pieces = split_text(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for idx, p in enumerate(pieces):
            meta = {"source": source, "chunk_index": idx}
            if product_id:
                meta["product_id"] = product_id
            if platform:
                meta["platform"] = platform
            if shop_id:
                meta["shop_id"] = shop_id
            chunks.append({"text": p, "metadata": meta})

    return chunks
