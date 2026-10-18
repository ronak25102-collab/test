from __future__ import annotations

import asyncio
import json
import re
from datetime import timedelta

import httpx
from pydantic import BaseModel, ValidationError

from signal_research.settings import Settings

from .base import LLMProvider, ProviderNotConfigured, ProviderUsage
from .structured import validate_response


class NvidiaRequestError(RuntimeError):
    code = "NVIDIA_REQUEST_FAILED"


class NvidiaTimeout(NvidiaRequestError):
    code = "NVIDIA_RESPONSE_TIMEOUT"


class NvidiaStructuredOutputError(NvidiaRequestError):
    """A received response cannot establish source evidence; never retry it."""
    code = "NVIDIA_INVALID_STRUCTURED_OUTPUT"


def check_status(status: int):
    if status == 200:
        return
    if status in {401, 403}:
        message = "NVIDIA authentication failed; check the API key and model access"
    elif status == 429:
        message = "NVIDIA quota exceeded; check your API Catalog limits before starting a new run"
    elif status == 503:
        message = "NVIDIA is temporarily unavailable (HTTP 503); start a new run after capacity recovers"
    elif status == 202:
        message = "NVIDIA returned a pending response; this request will not be submitted again automatically"
    else:
        message = f"NVIDIA request failed (HTTP {status})"
    raise NvidiaRequestError(message)


async def stream_payload(response: httpx.Response, max_output_tokens: int) -> dict:
    """Collect SSE privately; only a finished response may reach schema validation."""
    fragments, data = [], []
    usage, request_id, finish = {}, None, None
    size = 0
    async for line in response.aiter_lines():
        if line.startswith("data:"):
            data.append(line[5:].lstrip())
            size += len(line)
            if size > max_output_tokens * 128 + 65536:
                raise NvidiaRequestError("NVIDIA streamed response exceeded its size limit")
        elif not line and data:
            event = "\n".join(data)
            data.clear()
            if event == "[DONE]":
                if finish == "length":
                    raise NvidiaStructuredOutputError("NVIDIA reached its output token limit before completing structured output")
                if finish != "stop":
                    raise NvidiaRequestError("NVIDIA returned incomplete or refused structured output")
                return {"id": request_id, "usage": usage, "choices": [{
                    "finish_reason": finish, "message": {"content": "".join(fragments)},
                }]}
            chunk = json.loads(event)
            request_id = chunk.get("id") or request_id
            if chunk.get("usage"):
                usage = chunk["usage"]
            for choice in chunk.get("choices", []):
                if choice.get("index", 0) != 0:
                    raise NvidiaRequestError("NVIDIA returned unexpected output choices")
                delta = choice.get("delta", {})
                if delta.get("refusal"):
                    raise NvidiaRequestError("NVIDIA refused structured output")
                content = delta.get("content")
                if content is not None:
                    if not isinstance(content, str) or finish is not None:
                        raise NvidiaRequestError("NVIDIA returned invalid streamed output")
                    fragments.append(content)
                if choice.get("finish_reason") is not None:
                    finish = choice["finish_reason"]
    raise NvidiaRequestError("NVIDIA response stream ended before completion; start a new run to retry")


def nvidia_schema(original: dict) -> dict:
    """Generate Decimal values as numbers, avoiding an unsupported regex lookahead.

    Pydantic accepts Decimal as number|string, but its string pattern is rejected
    by NVIDIA's grammar decoder. Preserve numeric bounds and all other schema
    constraints. The original Pydantic model still validates returned output.
    """
    def convert(node):
        if isinstance(node, list):
            return [convert(item) for item in node]
        if not isinstance(node, dict):
            return node
        result = {key: convert(value) for key, value in node.items()}
        alternatives = result.get("anyOf", [])
        if any(item.get("type") == "number" for item in alternatives):
            retained = [item for item in alternatives if not (
                item.get("type") == "string" and
                item.get("pattern", "").startswith("^(?!^[-+.]*$)")
            )]
            if len(retained) != len(alternatives):
                if len(retained) == 1:
                    result.pop("anyOf")
                    result.update(retained[0])
                else:
                    result["anyOf"] = retained
        return result
    return convert(original)


class NvidiaProvider(LLMProvider):
    """NVIDIA hosted chat completions with native JSON schema and local validation."""

    endpoint = "https://integrate.api.nvidia.com/v1/chat/completions"
    protocol_version = "nvidia-validated-json-stream-v6"

    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, schema: type[BaseModel], messages: list[dict[str, str]], model_role: str,
                 deadline: timedelta, max_output_tokens: int):
        if not self.settings.nvidia_api_key:
            raise ProviderNotConfigured("NVIDIA_API_KEY is not configured")
        model = self.settings.model_for_role(model_role)
        if not model:
            raise ProviderNotConfigured(f"no NVIDIA model configured for role {model_role}")
        # The constrained decoder receives a schema, but the model also needs its
        # field names, types and formats in the prompt to choose meaningful values.
        guidance = ("Return only a populated DATA INSTANCE matching the schema below, never the schema itself. "
                    "Do not echo $defs, properties, required, type or other schema-definition keys. "
                    "Review verdict arrays must contain one entry per supplied candidate index, with the original index preserved. "
                    "Dates must use YYYY-MM-DD; "
                    "convert only complete dates explicitly present in the evidence. Populate available "
                    "fields rather than leaving explicit dates null. Never create a fact for an absent "
                    "metric. Numeric values must contain only the exact source number; put currency "
                    "and scale in their own fields. Use segment='all' for an entire issuer, never a "
                    "metric label. Copy evidence_quote verbatim, including the relevant headers, "
                    "or use null when the analyst instruction requests citation of the whole passage. "
                    "Schema: " + json.dumps(nvidia_schema(schema.model_json_schema())))
        prompted = [dict(message) for message in messages]
        if prompted and prompted[0]["role"] == "system":
            prompted[0]["content"] += "\n\n" + guidance
        else:
            prompted.insert(0, {"role": "system", "content": guidance})
        body = {
            "model": model,
            "messages": prompted,
            "max_tokens": max_output_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
            "temperature": 0,
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {
                "name": schema.__name__, "schema": nvidia_schema(schema.model_json_schema()),
            }},
        }
        if self.settings.nvidia_response_format == 'json_object':
            # Prompt carries the entire schema; original Pydantic validation and
            # all source/numerical/semantic gates remain identical. This avoids
            # compiling a new provider grammar for each dynamically cited schema.
            body['response_format'] = {'type': 'json_object'}
        if self.settings.nvidia_reasoning_budget is not None:
            body['reasoning_budget'] = self.settings.nvidia_reasoning_budget
        # DurableCalls reserves before transmission. Do not implicitly retry a
        # request or follow redirects carrying the authorization header.
        try:
            payload = asyncio.run(self._request(body, deadline, max_output_tokens))
            choice = payload["choices"][0]
            if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
                raise NvidiaStructuredOutputError("NVIDIA returned incomplete or refused structured output")
            content = choice["message"]["content"]
            if not isinstance(content, str):
                raise NvidiaRequestError("NVIDIA returned no structured output")
            fenced = re.fullmatch(r'\s*```(?:json)?\s*\n(\{.*\})\s*\n```\s*', content, re.S | re.I)
            if fenced:
                content = fenced[1]
            try:
                parsed = validate_response(schema, content)
            except ValidationError as error:
                fields = ', '.join('.'.join(map(str, e['loc'])) + ':' + e['type']
                                   for e in error.errors(include_input=False, include_url=False)[:3])
                raise NvidiaStructuredOutputError('NVIDIA returned invalid structured output (' + fields + ')') from None
            usage = payload.get("usage") or {}
            inputs, outputs = usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0)
            if any(type(value) is not int or value < 0 for value in (inputs, outputs)):
                raise NvidiaRequestError("NVIDIA returned invalid token usage")
        except (KeyError, IndexError, AttributeError, TypeError, ValueError, ValidationError):
            raise NvidiaRequestError("NVIDIA returned invalid structured output") from None
        # completion_tokens already includes any reasoning tokens. Missing usage
        # stays zero so the worker retains its conservative reservation.
        return parsed, ProviderUsage(input_tokens=inputs, output_tokens=outputs,
                                     request_id=payload.get("id"), status="ok")

    async def _request(self, body, deadline, max_output_tokens):
        seconds = deadline.total_seconds()
        try:
            # A read timeout alone resets on each chunk. This also bounds the
            # entire request, including connection, queueing and generation.
            async with asyncio.timeout(seconds):
                async with httpx.AsyncClient(timeout=httpx.Timeout(seconds, connect=min(10, seconds)),
                                             follow_redirects=False) as client:
                    async with client.stream("POST", self.endpoint, headers={
                        "Authorization": f"Bearer {self.settings.nvidia_api_key}",
                        "Accept": "text/event-stream, application/json",
                    }, json=body) as response:
                        check_status(response.status_code)
                        if "text/event-stream" in response.headers.get("content-type", ""):
                            return await stream_payload(response, max_output_tokens)
                        await response.aread()
                        return response.json()
        except (TimeoutError, httpx.TimeoutException):
            raise NvidiaTimeout(
                f"NVIDIA did not complete its response within {seconds:g} seconds; "
                "the request may have been processed. Start a new run to retry."
            ) from None
        except httpx.RequestError as exc:
            raise NvidiaRequestError(f"NVIDIA transport failed ({type(exc).__name__}); the request may have been processed") from None
