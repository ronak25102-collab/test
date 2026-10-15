"""Read-only, secret-free preflight; it never probes or bills providers."""
import json
from math import isfinite


def live_readiness(settings) -> dict:
    issues = []
    if settings.free_services_only and settings.llm_provider != "nvidia":
        issues.append("Free-only mode requires the NVIDIA hosted Developer Program prototype provider.")
    if settings.free_services_only and (settings.allow_unknown_cost or settings.max_run_cost_usd != 0 or settings.search_usd_per_credit != 0):
        issues.append("Free-only mode requires verified zero-dollar rates, MAX_RUN_COST_USD=0 and ALLOW_UNKNOWN_COST=false.")
    if not settings.llm_configured:
        issues.append(f"Configure {settings.llm_provider} credentials and both model roles.")
    nvidia_fallback = settings.llm_provider == "codecraft" and settings.codecraft_nvidia_fallback
    if nvidia_fallback and not (settings.nvidia_api_key and settings.nvidia_model_extract and settings.nvidia_model_research):
        issues.append("NVIDIA fallback requires NVIDIA_API_KEY and both NVIDIA model roles.")
    if not settings.tavily_api_key:
        issues.append("Configure TAVILY_API_KEY.")
    if not settings.allow_unknown_cost:
        try:
            card = json.loads(settings.model_rate_card_path.read_text(encoding="utf-8-sig"))
            if not isinstance(card, dict) or not isinstance(card.get("models"), list) or not all(isinstance(item, dict) for item in card["models"]):
                raise ValueError("The rate card requires a models list of model price objects.")
            if card.get("provider", settings.llm_provider) != settings.llm_provider:
                raise ValueError("The rate card provider does not match LLM_PROVIDER.")
            required_models = {settings.model_for_role("research"), settings.model_for_role("extract")}
            if nvidia_fallback:
                required_models.update({settings.nvidia_model_research, settings.nvidia_model_extract})
            for name in required_models:
                model = next((item for item in card["models"] if item.get("model_id") == name), None)
                if not model or any(type(model.get(key)) not in {int, float} or
                                    not isfinite(model[key]) or model[key] < 0 for key in
                                    ("input_usd_per_million_tokens", "output_usd_per_million_tokens")):
                    raise ValueError("The rate card needs finite, nonnegative prices for all configured primary and fallback models.")
            rate = settings.search_usd_per_credit
            if type(rate) not in {int, float} or not isfinite(rate) or rate < 0:
                raise ValueError("Configure SEARCH_USD_PER_CREDIT for your account.")
        except FileNotFoundError:
            issues.append("Create config/model-rates.json with your verified account prices.")
        except (OSError, ValueError, TypeError, KeyError, StopIteration) as exc:
            issues.append(str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError)
                          else "The model rate card is unreadable or malformed.")
    return {"ready": not issues, "issues": issues,
            "provider": settings.llm_provider,
            "max_run_seconds": settings.max_run_seconds,
            "model_request_timeout_seconds": settings.model_request_timeout_seconds,
            "codecraft_backup_keys": max(0, len([slot for slot, _ in settings.model_routes() if slot.startswith("codecraft:")]) - 1),
            "nvidia_fallback_enabled": nvidia_fallback,
            "cost_policy": "unknown prices; hard limits only" if settings.allow_unknown_cost else "account rate card",
            "demo_time_warning": settings.max_run_seconds > 480}
