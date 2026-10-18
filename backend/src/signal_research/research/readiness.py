"""Read-only, secret-free preflight; it never probes or bills providers."""
import json
from collections import Counter
from math import isfinite


def _codecraft_slots(settings) -> list[str]:
    return [slot for slot, _ in settings.model_routes() if slot.startswith('codecraft:')]


def _refused_keys(rejections: dict, settings) -> str | None:
    """'all 5 configured keys (4 out of credits (HTTP 402), 1 rejected (HTTP 401))'."""
    exhausted, rejected = rejections.get('exhausted', []), rejections.get('rejected', {})
    if not exhausted and not rejected:
        return None
    count, total = len(exhausted) + len(rejected), len(_codecraft_slots(settings))
    keys = 'key' if (total or count) == 1 else 'keys'
    scope = (f'all {total} configured {keys}' if total and count >= total else
             f'{count} of {total} configured {keys}' if total else f'{count} {keys}')
    details = [f'{len(exhausted)} out of credits (HTTP 402)'] if exhausted else []
    details += [f'{n} rejected (HTTP {status})'
                for status, n in sorted(Counter(rejected.values()).items(), key=lambda item: str(item[0]))]
    return f'{scope} ({", ".join(details)})'


def provider_cause(rejections: dict, settings, exc: Exception) -> str | None:
    """Plain-language root cause of a provider stop, from the run's durable routing records.

    None when no CodeCraft rejection or NVIDIA failure explains the stop.
    """
    parts = []
    refused = _refused_keys(rejections, settings)
    if refused:
        parts.append(f'CodeCraft refused {refused}')
    code = getattr(exc, 'code', '') or ''
    fallback = 'the NVIDIA fallback' if parts else 'NVIDIA'
    if code == 'NVIDIA_RESPONSE_TIMEOUT':
        parts.append(f'{fallback} did not finish its response in time')
    elif parts and code.startswith('NVIDIA'):
        parts.append(f'{fallback} did not return a usable response')
    if not parts:
        return None
    text = ', then '.join(parts)
    return text[0].upper() + text[1:]


def provider_warnings(store, settings) -> list[str]:
    """Non-blocking notices from the latest live run's recorded provider rejections.

    Credits can be restored at any time, so this never blocks a run; it explains
    what the next run is likely to meet. No provider is contacted.
    """
    if settings.llm_provider != 'codecraft':
        return []
    run_id = store.latest_live_run_id()
    if not run_id:
        return []
    refused = _refused_keys(store.provider_rejections(run_id), settings)
    if not refused:
        return []
    summary = store.get_summary(run_id)
    when = f' on {summary.started_at:%d %b %Y at %H:%M} UTC' if summary and summary.started_at else ''
    every = refused.startswith('all ')
    if every and settings.codecraft_nvidia_fallback:
        effect = 'New runs will use only the NVIDIA fallback until credits are added or the keys are replaced in .env.'
    elif every:
        effect = 'New runs will stop at their first model request until credits are added or the keys are replaced in .env.'
    else:
        effect = 'New runs will skip those keys after their first refusal.'
    return [f'The last live run{when} found CodeCraft refused {refused}. {effect}']


def live_readiness(settings) -> dict:
    issues = []
    if settings.free_services_only and settings.llm_provider != "nvidia":
        issues.append("Free-only mode requires the NVIDIA hosted Developer Program prototype provider.")
    if settings.free_services_only and (settings.allow_unknown_cost or settings.max_run_cost_usd != 0 or settings.search_usd_per_credit != 0):
        issues.append("Free-only mode requires verified zero-dollar rates, MAX_RUN_COST_USD=0 and ALLOW_UNKNOWN_COST=false.")
    if not settings.llm_configured:
        issues.append(f"Configure {settings.llm_provider} credentials and both model roles.")
    nvidia_fallback = settings.llm_provider == "codecraft" and settings.codecraft_nvidia_fallback
    if (nvidia_fallback or settings.nvidia_planning) and not (settings.nvidia_api_key and settings.nvidia_model_extract and settings.nvidia_model_research):
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
            if nvidia_fallback or settings.nvidia_planning:
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
            "max_run_seconds": min(settings.max_run_seconds, settings.demo_target_seconds),
            "model_request_timeout_seconds": settings.model_request_timeout_seconds,
            "codecraft_backup_keys": max(0, len([slot for slot, _ in settings.model_routes() if slot.startswith("codecraft:")]) - 1),
            "nvidia_fallback_enabled": nvidia_fallback,
            "nvidia_planning_enabled": settings.nvidia_planning,
            "cost_policy": "unknown prices; hard limits only" if settings.allow_unknown_cost else "account rate card",
            "demo_time_warning": False}
