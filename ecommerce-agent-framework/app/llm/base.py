from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseLLM(ABC):
    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """Send a list of chat messages to the selected model and return generated text."""
        raise NotImplementedError

    def generate(self, prompt: str, **kwargs) -> str:
        """Convenience wrapper for a single user-turn generation."""
        return self.chat([{"role": "user", "content": prompt}], **kwargs)
