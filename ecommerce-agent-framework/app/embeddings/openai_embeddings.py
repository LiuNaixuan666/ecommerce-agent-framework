from typing import List
from app.config import settings
from app.embeddings.base import BaseEmbedding

try:
    from langchain_community.embeddings import OpenAIEmbeddings as _OpenAIEmbeddings
except ImportError:
    from langchain.embeddings import OpenAIEmbeddings as _OpenAIEmbeddings


class OpenAIEmbeddingClient(BaseEmbedding):
    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured for embeddings")
        self.client = _OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            openai_api_key=settings.openai_api_key
        )

    def embed_documents(self, texts: List[str]):
        return self.client.embed_documents(texts)

    def embed_query(self, text: str):
        return self.client.embed_query(text)
