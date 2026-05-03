from abc import ABC, abstractmethod
from typing import List


class BaseEmbedding(ABC):
    @abstractmethod
    def embed_documents(self, texts: List[str]):
        raise NotImplementedError

    @abstractmethod
    def embed_query(self, text: str):
        raise NotImplementedError
