from typing import List, Dict, Any
from app.config import settings
from app.llm.base import BaseLLM


class GeminiClient(BaseLLM):
    def __init__(self):
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise ImportError("Gemini client requires google.generativeai package") from exc

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not configured")

        genai.configure(api_key=settings.gemini_api_key)
        self.genai = genai
        self.model = settings.gemini_model

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        prompt_lines = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            prompt_lines.append(f"{role.upper()}: {content}")

        prompt_text = "\n".join(prompt_lines)
        response = self.genai.generate(
            model=self.model,
            prompt=prompt_text,
            **{k: v for k, v in kwargs.items() if k != "response_format"}
        )

        return getattr(response, "text", str(response)).strip()
