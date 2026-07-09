from app.config import settings
from app.embeddings.local_embeddings import LocalTextEmbeddingClient
from app.embeddings.openai_embeddings import OpenAIEmbeddingClient


def get_embedding_client():
    provider = settings.embedding_provider.lower()
    if provider == "local":
        return LocalTextEmbeddingClient()
    if provider == "openai":
        return OpenAIEmbeddingClient()
    raise ValueError(f"Unsupported embedding provider: {settings.embedding_provider}")
