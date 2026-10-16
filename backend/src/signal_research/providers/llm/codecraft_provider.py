from __future__ import annotations

import asyncio
import json
import re
from datetime import timedelta

import httpx
from pydantic import BaseModel, ValidationError

from signal_research.settings import Settings

from .base import LLMProvider, ProviderNotConfigured, ProviderUsage


class CodeCraftError(RuntimeError):
    code = "CODECRAFT_REQUEST_FAILED"


class CodeCraftStructuredOutputError(CodeCraftError):
    """A received response cannot establish evidence; never accept partial JSON."""
    code = "CODECRAFT_INVALID_STRUCTURED_OUTPUT"


class CodeCraftTimeout(CodeCraftError):
    code = 'CODECRAFT_TIMEOUT'


class CodeCraftCreditsExhausted(CodeCraftError):
    """Explicit HTTP 402 rejection, distinct from throttling or uncertain work."""
    code = "CODECRAFT_CREDITS_EXHAUSTED"
    provider_usage = ProviderUsage(status="rejected_http_402")


class CodeCraftProvider(LLMProvider):
    """Documented JSON mode with original local schema and evidence validation."""

    endpoint = "https://www.codecraftapi.com/v1/chat/completions"
    protocol_version = "codecraft-validated-json-v2"

    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, schema: type[BaseModel], messages: list[dict[str, str]], model_role: str,
                 deadline: timedelta, max_output_tokens: int):
        if not self.settings.codecraft_api_key or not self.settings.model_for_role(model_role):
            raise ProviderNotConfigured("CodeCraft key and model role must be configured")
        # CodeCraft raises smaller budgets to 2048. Never send a request whose
        # provider minimum could exceed the remaining durable token allowance.
        if max_output_tokens < 2048:
            from signal_research.domain.errors import BudgetExceeded
            raise BudgetExceeded("CodeCraft requires at least 2048 remaining output tokens")
        guidance = (
            "Return only a JSON object matching the schema below, without Markdown. "
            "Dates must be YYYY-MM-DD and explicitly supported by the supplied evidence. "
            "Copy evidence quotes verbatim. Be concise. Never invent absent facts or IDs. "
            "Use segment='all' for an entire issuer. Keep currency and scale separate from "
            "numeric values. Schema: " + json.dumps(schema.model_json_schema())
        )
        prompted = [dict(message) for message in messages]
        if prompted and prompted[0]["role"] == "system":
            prompted[0]["content"] += "\n\n" + guidance
        else:
            prompted.insert(0, {"role": "system", "content": guidance})
        body = {"model": self.settings.model_for_role(model_role), "messages": prompted,
                "max_tokens": max_output_tokens, "temperature": 0, "stream": False,
                "response_format": {"type": "json_object"}}
        payload = asyncio.run(self._request(body, deadline))
        try:
            counts = payload["usage"]
            inputs, outputs = counts["prompt_tokens"], counts["completion_tokens"]
            if any(type(value) is not int or value < 0 for value in (inputs, outputs)):
                raise ValueError
            usage = ProviderUsage(input_tokens=inputs, output_tokens=outputs,
                                  request_id=payload.get("id"), status="ok")
        except (KeyError, TypeError, ValueError):
            raise CodeCraftError("CodeCraft returned missing or invalid token usage") from None
        try:
            choice = payload["choices"][0]
            if choice.get("finish_reason") == "length":
                error = CodeCraftStructuredOutputError("CodeCraft reached its output token limit before completing structured output")
                error.provider_usage = usage
                raise error
            if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
                raise ValueError
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise ValueError
            fence = re.fullmatch(r"\s*```(?:json)?\s*(\{[\s\S]*\})\s*```\s*", content)
            if fence:
                content = fence[1]
            parsed = schema.model_validate_json(content)
        except (KeyError, IndexError, AttributeError, TypeError, ValueError, ValidationError) as cause:
            detail = ''
            if isinstance(cause, ValidationError):
                detail = ' (' + ', '.join('.'.join(str(part) for part in issue['loc']) + ':' + issue['type']
                    for issue in cause.errors(include_input=False, include_url=False)[:3]) + ')'
            error = CodeCraftStructuredOutputError("CodeCraft returned incomplete or invalid structured output" + detail)
            # Completed but invalid responses still consume tokens. Preserve the
            # provider's usage without accepting their content as research evidence.
            error.provider_usage = usage
            raise error from None
        return parsed, usage

    async def _request(self, body, deadline):
        seconds = deadline.total_seconds()
        try:
            async with asyncio.timeout(seconds):
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(seconds, connect=min(10, seconds)),
                    follow_redirects=False,
                ) as client:
                    response = await client.post(self.endpoint, headers={
                        "Authorization": f"Bearer {self.settings.codecraft_api_key}",
                    }, json=body)
                    if response.status_code != 200:
                        if response.status_code == 402:
                            raise CodeCraftCreditsExhausted("CodeCraft token allowance and balance exhausted (HTTP 402)")
                        explanations = {401: "authentication failed", 403: "access denied",
                                        404: "model unavailable", 429: "rate or quota limit reached"}
                        detail = explanations.get(response.status_code, "request failed")
                        raise CodeCraftError(f"CodeCraft {detail} (HTTP {response.status_code})")
                    return response.json()
        except (TimeoutError, httpx.TimeoutException):
            raise CodeCraftTimeout(
                f"CodeCraft did not complete within {seconds:g} seconds; the request may have "
                "been processed and will not be retried automatically"
            ) from None
        except httpx.RequestError as error:
            raise CodeCraftError(f"CodeCraft transport failed ({type(error).__name__})") from None
        except ValueError:
            raise CodeCraftError("CodeCraft returned an invalid response envelope") from None
