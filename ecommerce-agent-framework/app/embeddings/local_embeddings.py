import hashlib
import math
import re
from typing import List

from app.embeddings.base import BaseEmbedding


class LocalTextEmbeddingClient(BaseEmbedding):
    """Deterministic local text embeddings for offline development.

    This is a lightweight hashed n-gram embedding. It is not as semantic as a
    hosted embedding model, but it keeps ingestion and retrieval usable without
    network calls.
    """

    def __init__(self, dimension: int = 768):
        self.dimension = dimension

    def _tokens(self, text: str) -> List[str]:
        lowered = text.lower()
        ascii_tokens = re.findall(r"[a-z0-9_]+", lowered)
        cjk_chars = re.findall(r"[\u4e00-\u9fff]", lowered)
        cjk_bigrams = ["".join(cjk_chars[i:i + 2]) for i in range(max(0, len(cjk_chars) - 1))]
        return ascii_tokens + cjk_chars + cjk_bigrams

    def _embed_text(self, text: str) -> List[float]:
        vector = [0.0] * self.dimension
        for token in self._tokens(text):
            digest = hashlib.md5(token.encode("utf-8")).hexdigest()
            index = int(digest, 16) % self.dimension
            vector[index] += 1.0

        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def embed_documents(self, texts: List[str]):
        return [self._embed_text(text) for text in texts]

    def embed_query(self, text: str):
        return self._embed_text(text)
