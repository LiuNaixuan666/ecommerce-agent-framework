# ingestion.py
import os
import logging
from typing import Optional, List
from .document_parser import DocumentParser
from .chunking import split_documents
from ..rag.vector_store import get_or_create_chroma
from app.embeddings.factory import get_embedding_client

logger = logging.getLogger(__name__)


def ingest_merchant_documents(
	merchant_id: str,
	merchant_dir: Optional[str] = None,
	embeddings=None,
	chunk_size: int = 1000,
	chunk_overlap: int = 200,
	persist_root: Optional[str] = None,
) -> dict:
	"""
	将指定商家目录下的文档接入向量库：
	1) 解析文档（PDF/CSV/...）
	2) 使用 RecursiveCharacterTextSplitter 切分文本
	3) 将切分后的片段写入 Chroma 向量库（按 merchant_id 命名）

	返回一个简要结果统计。
	"""
	if merchant_dir is None:
		merchant_dir = os.path.join(os.getcwd(), "data", "merchants", merchant_id)

	parser = DocumentParser()
	documents = parser.load_merchant_data(merchant_dir)

	if not documents:
		return {"status": "no_documents", "count": 0}

	chunks = split_documents(documents, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

	if embeddings is None:
		embeddings = get_embedding_client()

	# 默认将向量库持久化在商家目录下的 vector_store 以保持与 data 布局一致
	if persist_root is None:
		persist_root = os.path.join(merchant_dir, "vector_store")

	chroma = get_or_create_chroma(merchant_id, embeddings, persist_root=persist_root)

	texts: List[str] = [c["text"] for c in chunks]
	metadatas: List[dict] = [c["metadata"] for c in chunks]

	# 保证长度一致，若不一致则截断到最小长度并记录警告
	if len(texts) != len(metadatas):
		min_len = min(len(texts), len(metadatas))
		logger.warning("texts and metadatas length mismatch, truncating to %s", min_len)
		texts = texts[:min_len]
		metadatas = metadatas[:min_len]

	if not texts:
		return {"status": "no_chunks", "documents": len(documents), "chunks": 0}

	try:
		chroma.add_texts(texts=texts, metadatas=metadatas)
	except Exception as e:
		logger.exception("Failed to add_texts to chroma: %s", e)
		return {"status": "error", "detail": f"add_texts_failed: {e}"}

	# 某些 Chroma 实现需要显式 persist()
	try:
		chroma.persist()
	except Exception as e:
		# 记录但不阻塞流程
		logger.warning("Chroma persist() raised: %s", e)

	return {"status": "ok", "documents": len(documents), "chunks": len(texts), "persist_root": persist_root}

