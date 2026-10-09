from signal_research.settings import Settings

from .base import LLMProvider
from .gemini_provider import GeminiProvider
from .openai_provider import OpenAIProvider


def get_llm_provider(settings: Settings) -> LLMProvider:
    return GeminiProvider(settings) if settings.llm_provider == "gemini" else OpenAIProvider(settings)
