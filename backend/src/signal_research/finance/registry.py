from dataclasses import dataclass

from signal_research.domain.enums import Profile


@dataclass(frozen=True)
class MetricDefinition:
    key: str
    aliases: tuple[str, ...]
    unit: str
    kind: str
    profiles: tuple[Profile, ...]
    preferred_evidence: str
    hazards: tuple[str, ...] = ()


COMMON = (Profile.BANK, Profile.NBFC, Profile.LIFE_INSURER, Profile.GENERAL_INSURER, Profile.EXCHANGE, Profile.ASSET_MANAGER, Profile.DIVERSIFIED)

METRICS: dict[str, MetricDefinition] = {
    "gross_advances": MetricDefinition("gross_advances", ("advances", "gross loans"), "INR_crore", "stock", (Profile.BANK, Profile.NBFC), "quarterly results"),
    "deposits": MetricDefinition("deposits", ("total deposits",), "INR_crore", "stock", (Profile.BANK,), "quarterly results"),
    "casa_ratio": MetricDefinition("casa_ratio", ("CASA",), "percent", "stock", (Profile.BANK,), "investor presentation"),
    "nim": MetricDefinition("nim", ("net interest margin",), "percent", "duration", (Profile.BANK, Profile.NBFC), "quarterly results"),
    "gnpa": MetricDefinition("gnpa", ("gross NPA",), "percent", "stock", (Profile.BANK, Profile.NBFC), "asset-quality disclosure"),
    "aum": MetricDefinition("aum", ("assets under management",), "INR_crore", "stock", (Profile.NBFC, Profile.ASSET_MANAGER), "quarterly results"),
    "vnb": MetricDefinition("vnb", ("value of new business",), "INR_crore", "duration", (Profile.LIFE_INSURER,), "annual report"),
    "ape": MetricDefinition("ape", ("annual premium equivalent",), "INR_crore", "duration", (Profile.LIFE_INSURER,), "annual report"),
    "combined_ratio": MetricDefinition("combined_ratio", ("combined ratio",), "percent", "duration", (Profile.GENERAL_INSURER,), "annual report"),
    "transaction_revenue": MetricDefinition("transaction_revenue", ("transaction fees",), "INR_crore", "duration", (Profile.EXCHANGE,), "quarterly results"),
    "average_aum": MetricDefinition("average_aum", ("average AUM",), "INR_crore", "duration", (Profile.ASSET_MANAGER,), "quarterly results"),
    "segment_profit": MetricDefinition("segment_profit", ("segment profit",), "INR_crore", "duration", COMMON, "segment disclosure"),
}


def metrics_for_profile(profile: Profile) -> list[MetricDefinition]:
    return [metric for metric in METRICS.values() if profile in metric.profiles]


def resolve_metric(text: str) -> MetricDefinition | None:
    lowered = text.lower()
    for metric in METRICS.values():
        if lowered == metric.key or any(alias.lower() in lowered for alias in metric.aliases):
            return metric
    return None
