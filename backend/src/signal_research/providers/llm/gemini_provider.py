"""Stateless structured Gemini requests through the supported generateContent REST API."""
from __future__ import annotations

from datetime import timedelta
from urllib.parse import quote

import httpx
from pydantic import BaseModel

from signal_research.settings import Settings

from .base import LLMProvider, ProviderNotConfigured, ProviderUsage


class GeminiRequestError(RuntimeError):
    code = "GEMINI_REQUEST_FAILED"


class GeminiUnavailable(GeminiRequestError):
    """An explicit HTTP 503 response, rather than an uncertain transport failure."""
    code = "GEMINI_TEMPORARILY_UNAVAILABLE"


def gemini_schema(original: dict) -> dict:
    """Inline local definitions and remove unsupported wire constraints.

    The original Pydantic schema still validates every returned value. This
    translation affects only the provider's constrained decoder, not publication.
    """
    definitions = original.get("$defs", {})
    # The native Schema decoder rejects some otherwise valid JSON Schema constraints.
    # Keep its structural subset and leave exact bounds/formats to Pydantic validation.
    allowed = {"type", "description", "properties", "items", "enum"}

    def convert(node, ancestors=()):
        if "$ref" in node:
            reference = node["$ref"]
            if not reference.startswith("#/$defs/") or reference in ancestors:
                raise ValueError("Gemini schemas require non-recursive local definitions")
            name = reference.rsplit("/", 1)[-1]
            node = definitions[name] | {k: v for k, v in node.items() if k != "$ref"}
            ancestors = (*ancestors, reference)
        if "anyOf" in node:
            alternatives = node["anyOf"]
            values = [option for option in alternatives if option.get("type") != "null"]
            nullable = len(values) != len(alternatives)
            if len(values) == 1:
                selected = values[0]
            elif {v.get("type") for v in values} == {"number", "string"}:
                # Pydantic represents Decimal as number|string. Numeric confidence
                # is generated as a number and checked as Decimal on return.
                selected = next(v for v in values if v.get("type") == "number")
            else:
                raise ValueError("Gemini schema contains an unsupported multi-type union")
            node = selected | {k: v for k, v in node.items() if k != "anyOf"}
            result = convert(node, ancestors)
            if nullable:
                result["nullable"] = True
            return result
        result = {k: v for k, v in node.items() if k in allowed}
        if "type" in result:
            result["type"] = result["type"].upper()
        guidance = []
        if node.get("format"):
            guidance.append(f"Required value format: {node['format']}.")
        for constraint, label in (("minimum", "Minimum value"), ("maximum", "Maximum value"),
                                  ("minItems", "Minimum item count"), ("maxItems", "Maximum item count")):
            if constraint in node:
                guidance.append(f"{label}: {node[constraint]}.")
        if guidance:
            result["description"] = " ".join([node.get("description", ""), *guidance]).strip()
        if "properties" in result:
            result["properties"] = {k: convert(v, ancestors) for k, v in result["properties"].items()}
            # Explicit nullable values reduce optional-field decoding complexity.
            result["required"] = list(result["properties"])
        if isinstance(result.get("items"), dict):
            result["items"] = convert(result["items"], ancestors)
        return result

    return convert(original)


class GeminiProvider(LLMProvider):
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models"
    protocol_version = "generate-content-native-schema-v2"

    def __init__(self, settings: Settings):
        self.settings = settings

    def generate(self, schema: type[BaseModel], messages: list[dict[str, str]], model_role: str,
                 deadline: timedelta, max_output_tokens: int):
        from signal_research.precomputed.guard import require_network_allowed
        require_network_allowed()
        if not self.settings.gemini_api_key:
            raise ProviderNotConfigured("GEMINI_API_KEY is not configured")
        model = self.settings.model_for_role(model_role)
        if not model:
            raise ProviderNotConfigured(f"no Gemini model configured for role {model_role}")
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        inputs = [m for m in messages if m["role"] != "system"]
        if not inputs or any(m["role"] != "user" for m in inputs):
            raise ValueError("Gemini analyst requests require user inputs and system instructions")
        body = {
            "contents": [{"role": "user", "parts": [{"text": m["content"]}]} for m in inputs],
            "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {
                "maxOutputTokens": max_output_tokens,
                "thinkingConfig": {"thinkingLevel": self.settings.gemini_thinking_level.upper()},
                "responseMimeType": "application/json",
                "responseSchema": gemini_schema(schema.model_json_schema()),
            },
        }
        if not system:
            body.pop("systemInstruction")
        # No implicit retries: DurableCalls reserves each request before transmission.
        try:
            with httpx.Client(timeout=deadline.total_seconds(), follow_redirects=False) as client:
                endpoint = f"{self.endpoint}/{quote(model.removeprefix('models/'), safe='')}:generateContent"
                response = client.post(endpoint, headers={
                    "x-goog-api-key": self.settings.gemini_api_key,
                }, json=body)
        except httpx.RequestError as exc:
            raise GeminiRequestError(f"Gemini transport failed ({type(exc).__name__}); the request may have been processed") from None
        if not response.is_success:
            if response.status_code == 503:
                raise GeminiUnavailable("Gemini is temporarily unavailable (HTTP 503); try again after capacity recovers")
            if response.status_code == 429:
                message = "Gemini quota exceeded; inspect your AI Studio limits before starting a new run"
            elif response.status_code in {401, 403}:
                message = "Gemini authentication or model access rejected; check the local key and account permissions"
            elif response.status_code in {500, 502, 503, 504}:
                message = f"Gemini is temporarily unavailable (HTTP {response.status_code}); start a new run after capacity recovers"
            else:
                message = f"Gemini request rejected (HTTP {response.status_code}); check the configured model and schema"
            # Provider error bodies can contain sensitive request details; do not log them.
            raise GeminiRequestError(message)
        payload = response.json()
        candidates = payload.get("candidates", [])
        if not candidates or candidates[0].get("finishReason") != "STOP":
            raise GeminiRequestError("Gemini did not complete the structured response within its output limit")
        text = "".join(part.get("text", "") for part in candidates[0].get("content", {}).get("parts", [])
                       if not part.get("thought", False))
        if not text:
            raise GeminiRequestError("Gemini returned no structured text output")
        usage = payload.get("usageMetadata", {})
        # Thinking consumes the output allowance and must be included in the ledger.
        output_tokens = usage.get("candidatesTokenCount", 0) + usage.get("thoughtsTokenCount", 0)
        return schema.model_validate_json(text), ProviderUsage(
            input_tokens=usage.get("promptTokenCount", 0), output_tokens=output_tokens,
            request_id=payload.get("responseId"), status="ok",
        )
