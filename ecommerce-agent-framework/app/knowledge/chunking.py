# chunking.py
from typing import List, Dict
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


def split_documents(documents: List[Dict], chunk_size: int = 1000, chunk_overlap: int = 200) -> List[Dict]:
	"""
	接收 parse 后的文档列表，返回切分后的片段列表。

	输入 documents 格式: [{"source": "filename", "content": "..."}, ...]
	返回格式: [{"text": "chunk_text", "metadata": {"source": filename, "chunk_index": i}}, ...]
	"""
	chunks = []
	for doc in documents:
		source = doc.get("source", "unknown")
		content = doc.get("content", "")
		if not content:
			continue

		pieces = split_text(content, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
		for idx, p in enumerate(pieces):
			chunks.append({"text": p, "metadata": {"source": source, "chunk_index": idx}})

	return chunks
