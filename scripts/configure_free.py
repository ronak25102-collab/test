"""Verify existing free-account access before creating a private zero-dollar card."""
import json
from datetime import UTC, datetime, timedelta

from pydantic import BaseModel
from signal_research.providers.llm.nvidia_provider import NvidiaProvider
from signal_research.providers.search.account import free_account_usage
from signal_research.settings import get_settings


class AccessProbe(BaseModel):
    accessible: bool


def main():
    settings = get_settings()
    if settings.llm_provider != 'nvidia':
        raise RuntimeError('Only the documented NVIDIA hosted free prototype service is authorized')
    remaining = free_account_usage(settings)
    if remaining < 1:
        raise RuntimeError('No included free Tavily search credits remain')
    adapter = NvidiaProvider(settings)
    _, usage = adapter.generate(AccessProbe, [{'role': 'user', 'content': 'Return accessible=true.'}],
                               'research', timedelta(seconds=45), 128)
    verified = datetime.now(UTC).isoformat()
    card = {'provider': 'nvidia', 'account_scope': 'NVIDIA Developer Program hosted prototype API only',
            'verified_at': verified,
            'verification_basis': 'Official documentation declares free Developer Program hosted prototyping; authenticated access probe succeeded. Remaining NVIDIA quota is not verified.',
            'models': [{'model_id': model, 'input_usd_per_million_tokens': 0,
                'output_usd_per_million_tokens': 0, 'currency': 'USD',
                'official_pricing_url': 'https://docs.api.nvidia.com/nim/docs/run-anywhere'}
                for model in sorted({settings.model_for_role('research'), settings.model_for_role('extract')})]}
    settings.model_rate_card_path.parent.mkdir(parents=True, exist_ok=True)
    settings.model_rate_card_path.write_text(json.dumps(card, indent=2), encoding='utf-8')
    print(json.dumps({'verified_at': verified, 'free_tavily_credits_remaining': remaining,
        'nvidia_authenticated_access': True, 'nvidia_quota': 'NOT VERIFIED: no documented quota endpoint',
        'probe_input_tokens': usage.input_tokens, 'probe_output_tokens': usage.output_tokens,
        'rate_card_path': str(settings.model_rate_card_path)}, indent=2))


if __name__ == '__main__':
    main()
