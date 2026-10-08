from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    request_id: str | None = None
    status: str = "ok"
    cost_status: str = "unknown"


class ProviderNotConfigured(RuntimeError):
    code = "PROVIDER_NOT_CONFIGURED"


class LLMProvider:
    def generate(self, schema: type[T], messages: list[dict[str, str]], model_role: str,
                 deadline: timedelta, max_output_tokens: int) -> tuple[T, ProviderUsage]:
        raise NotImplementedError
