from app.config import settings
from app.llm.openai_client import OpenAIClient
from app.llm.gemini_client import GeminiClient


def get_llm():
    provider = settings.llm_provider.lower()
    if provider == "gemini":
        return GeminiClient()
    return OpenAIClient()
