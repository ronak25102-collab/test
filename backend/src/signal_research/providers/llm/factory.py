from signal_research.settings import Settings

from .base import LLMProvider
from .gemini_provider import GeminiProvider
from .nvidia_provider import NvidiaProvider
from .openai_provider import OpenAIProvider


def get_llm_provider(settings: Settings) -> LLMProvider:
    providers = {"gemini": GeminiProvider, "nvidia": NvidiaProvider, "openai": OpenAIProvider}
    return providers[settings.llm_provider](settings)
