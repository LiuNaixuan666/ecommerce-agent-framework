from app.config import settings
from app.llm.openai_client import OpenAIClient
from app.llm.gemini_client import GeminiClient
from app.llm.local_client import LocalLLMClient


def get_llm():
    provider = settings.llm_provider.lower()
    if provider == "local":
        return LocalLLMClient()
    if provider == "gemini":
        return GeminiClient()
    return OpenAIClient()
