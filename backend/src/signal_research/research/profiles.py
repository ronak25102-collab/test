from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from signal_research.domain.enums import Profile
from signal_research.finance.registry import metrics_for_profile


@dataclass(frozen=True)
class ProfileConfig:
    profile: Profile
    required_metrics: tuple[str, ...]
    aliases: dict[str, tuple[str, ...]]
    starter_questions: tuple[str, ...]
    calculation_ids: tuple[str, ...]
    peer_criteria: str


PROFILE_CONFIGS: dict[Profile, ProfileConfig] = {
    Profile.BANK: ProfileConfig(Profile.BANK, ("gross_advances", "deposits", "casa_ratio", "nim", "gnpa"), {"advances": ("gross advances", "loans"), "deposits": ("total deposits",)}, ("Does loan growth outpace stable funding?", "Does headline asset quality conceal weaker inflows or write-offs?"), ("yoy_growth", "loan_to_deposit", "change_pp"), "bank with comparable reporting scope"),
    Profile.NBFC: ProfileConfig(Profile.NBFC, ("aum", "gnpa", "nim"), {"aum": ("assets under management",), "stage_3": ("stage 3",)}, ("Is funding becoming more concentrated?", "Is growth migrating to a riskier product or borrower mix?"), ("yoy_growth", "change_pp"), "lender with matching AUM/on-book definitions"),
    Profile.LIFE_INSURER: ProfileConfig(Profile.LIFE_INSURER, ("ape", "vnb"), {"ape": ("annual premium equivalent",), "vnb": ("value of new business",)}, ("Does premium growth translate into new-business value?", "Is product or distribution mix changing profitability?"), ("yoy_growth", "share_pct"), "life insurer with matching APE convention"),
    Profile.GENERAL_INSURER: ProfileConfig(Profile.GENERAL_INSURER, ("combined_ratio",), {"earned_premium": ("earned premium",), "claims": ("claims ratio",)}, ("Is growth improving underwriting economics?", "Do reserve changes explain earnings movement?"), ("change_pp",), "general insurer with matching denominator"),
    Profile.EXCHANGE: ProfileConfig(Profile.EXCHANGE, ("transaction_revenue",), {"turnover": ("turnover",), "contracts": ("contracts traded",)}, ("Are earnings driven by durable fee income or volume mix?", "What changes after a rule becomes effective?"), ("yoy_growth", "share_pct"), "market infrastructure business with same fee denominator"),
    Profile.ASSET_MANAGER: ProfileConfig(Profile.ASSET_MANAGER, ("average_aum",), {"net_flows": ("net flows",), "fee_income": ("fee income",)}, ("Is revenue growth caused by market appreciation rather than flows?", "Is product mix lowering fee realization?"), ("yoy_growth",), "asset manager with matching average AUM"),
    Profile.DIVERSIFIED: ProfileConfig(Profile.DIVERSIFIED, ("segment_profit",), {"segment_revenue": ("segment revenue",), "active_clients": ("active clients",)}, ("Do segment economics explain a change hidden in consolidated totals?", "Do group dependencies or related-party flows matter?"), ("share_pct", "yoy_growth"), "same segment and reporting scope"),
}


def profile_for(value: str | Profile) -> ProfileConfig:
    profile = Profile(value)
    base = PROFILE_CONFIGS[profile]
    path = Path(__file__).parents[1] / "profiles" / f"{profile.value}.yaml"
    if not path.exists():
        return base
    data = yaml.safe_load(path.read_text()) or {}
    aliases = {key: tuple(values) for key, values in (data.get("aliases") or {}).items()}
    return ProfileConfig(
        profile=profile,
        required_metrics=tuple(data.get("required_metrics") or base.required_metrics),
        aliases=aliases or base.aliases,
        starter_questions=tuple(data.get("starter_questions") or base.starter_questions),
        calculation_ids=tuple(data.get("calculation_ids") or base.calculation_ids),
        peer_criteria=data.get("peer_criteria") or base.peer_criteria,
    )


def available_metric_keys(profile: Profile) -> list[str]:
    return [metric.key for metric in metrics_for_profile(profile)]
