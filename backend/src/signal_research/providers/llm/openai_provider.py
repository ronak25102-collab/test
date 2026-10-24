from __future__ import annotations

from datetime import timedelta

from pydantic import BaseModel

from signal_research.settings import Settings

from .base import LLMProvider, ProviderNotConfigured, ProviderUsage


class OpenAIProvider(LLMProvider):
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, schema: type[BaseModel], messages: list[dict[str, str]], model_role: str,
                 deadline: timedelta, max_output_tokens: int):
        from signal_research.precomputed.guard import require_network_allowed
        require_network_allowed()
        if not self.settings.openai_api_key:
            raise ProviderNotConfigured("OPENAI_API_KEY is not configured")
        model = self.settings.openai_model_extract if model_role == "extract" else self.settings.openai_model_research
        if not model:
            raise ProviderNotConfigured(f"no model configured for role {model_role}")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderNotConfigured("install the optional OpenAI SDK to enable live model calls") from exc
        client = OpenAI(api_key=self.settings.openai_api_key, timeout=deadline.total_seconds(), max_retries=0)
        response = client.responses.parse(
            model=model,
            input=messages,
            text_format=schema,
            max_output_tokens=max_output_tokens,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError("model returned no parsed structured output")
        usage = getattr(response, "usage", None)
        return parsed, ProviderUsage(
            input_tokens=getattr(usage, "input_tokens", 0) if usage else 0,
            output_tokens=getattr(usage, "output_tokens", 0) if usage else 0,
            request_id=getattr(response, "id", None),
            status="ok",
        )
