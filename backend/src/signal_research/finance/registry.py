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
    "advances_as_reported": MetricDefinition("advances_as_reported", ("advances",), "INR_crore", "stock", (Profile.BANK,), "audited balance sheet", ("do not infer gross or net definition",)),
    "credit_deposit_ratio": MetricDefinition("credit_deposit_ratio", ("credit-deposit ratio", "credit deposit ratio", "loan-to-deposit ratio"), "percent", "stock", (Profile.BANK,), "issuer ratio disclosure"),
    "gross_advances": MetricDefinition("gross_advances", ("gross advances", "gross loans"), "INR_crore", "stock", (Profile.BANK, Profile.NBFC), "quarterly results"),
    "deposits": MetricDefinition("deposits", ("total deposits",), "INR_crore", "stock", (Profile.BANK,), "quarterly results"),
    "casa_ratio": MetricDefinition("casa_ratio", ("CASA",), "percent", "stock", (Profile.BANK,), "investor presentation"),
    "nim": MetricDefinition("nim", ("net interest margin",), "percent", "duration", (Profile.BANK, Profile.NBFC), "quarterly results"),
    "gnpa": MetricDefinition("gnpa", ("gross NPA",), "percent", "stock", (Profile.BANK, Profile.NBFC), "asset-quality disclosure"),
    "aum": MetricDefinition("aum", ("assets under management",), "INR_crore", "stock", (Profile.NBFC, Profile.ASSET_MANAGER, Profile.LIFE_INSURER), "quarterly results"),
    "vnb": MetricDefinition("vnb", ("value of new business",), "INR_crore", "duration", (Profile.LIFE_INSURER,), "annual report"),
    "ape": MetricDefinition("ape", ("annual premium equivalent", "annualised premium equivalent", "annualized premium equivalent"), "INR_crore", "duration", (Profile.LIFE_INSURER,), "annual report"),
    "combined_ratio": MetricDefinition("combined_ratio", ("combined ratio",), "percent", "duration", (Profile.GENERAL_INSURER,), "annual report"),
    "transaction_revenue": MetricDefinition("transaction_revenue", ("transaction fees",), "INR_crore", "duration", (Profile.EXCHANGE,), "quarterly results"),
    "average_aum": MetricDefinition("average_aum", ("average AUM",), "INR_crore", "duration", (Profile.ASSET_MANAGER,), "quarterly results"),
    "segment_profit": MetricDefinition("segment_profit", ("segment profit",), "INR_crore", "duration", COMMON, "segment disclosure"),
}

# Profile-native measures are registered centrally, never added for a specific issuer.
for key, aliases, unit, kind, profiles in (
    ("net_advances", ("net advances", "net loans"), "INR_crore", "stock", (Profile.BANK,)),
    ("on_book_loans", ("on-book loans", "on book loans", "loan assets"), "INR_crore", "stock", (Profile.NBFC,)),
    ("net_flows", ("net flows", "net inflows"), "INR_crore", "duration", (Profile.ASSET_MANAGER,)),
    ("earned_premium", ("net earned premium", "earned premium"), "INR_crore", "duration", (Profile.GENERAL_INSURER,)),
    ("trading_turnover", ("trading turnover", "transaction turnover"), "INR_crore", "duration", (Profile.EXCHANGE,)),
    ("new_business_premium", ("new business premium",), "INR_crore", "duration", (Profile.LIFE_INSURER,)),
    ("renewal_premium", ("renewal premium",), "INR_crore", "duration", (Profile.LIFE_INSURER,)),
    ("total_premium", ("total premium", "total premium income"), "INR_crore", "duration", (Profile.LIFE_INSURER,)),
    ("persistency_13m", ("13th month persistency", "13-month persistency", "13 month persistency"), "percent", "stock", (Profile.LIFE_INSURER,)),
    ("persistency_61m", ("61st month persistency", "61-month persistency", "61 month persistency"), "percent", "stock", (Profile.LIFE_INSURER,)),
    ("co_lending_aum", ("co-lending AUM", "co lending assets"), "INR_crore", "stock", (Profile.NBFC,)),
    ("bank_borrowings", ("borrowings from banks", "bank borrowings"), "INR_crore", "stock", (Profile.NBFC, Profile.DIVERSIFIED)),
    ("bond_borrowings", ("debt securities", "bonds and debentures"), "INR_crore", "stock", (Profile.NBFC, Profile.DIVERSIFIED)),
    ("segment_revenue", ("segment revenue",), "INR_crore", "duration", (Profile.DIVERSIFIED,)),
    ("funding_cost", ("cost of funds", "funding cost"), "percent", "duration", (Profile.BANK, Profile.NBFC)),
    ("credit_cost", ("credit cost",), "percent", "duration", (Profile.BANK, Profile.NBFC)),
    ("nnpa", ("net NPA", "net non-performing assets ratio"), "percent", "stock", (Profile.BANK, Profile.NBFC)),
    ("stage2_ratio", ("stage 2 ratio", "stage-2 ratio"), "percent", "stock", (Profile.NBFC,)),
    ("stage3_ratio", ("stage 3 ratio", "stage-3 ratio"), "percent", "stock", (Profile.NBFC,)),
    ("borrowings", ("total borrowings", "borrowings"), "INR_crore", "stock", (Profile.BANK, Profile.NBFC, Profile.DIVERSIFIED)),
    ("vnb_margin", ("VNB margin", "value of new business margin"), "percent", "duration", (Profile.LIFE_INSURER,)),
    ("persistency_ratio", ("persistency ratio",), "percent", "duration", (Profile.LIFE_INSURER,)),
    ("solvency_ratio", ("solvency ratio",), "percent", "stock", (Profile.LIFE_INSURER, Profile.GENERAL_INSURER)),
    ("gross_written_premium", ("gross written premium",), "INR_crore", "duration", (Profile.GENERAL_INSURER,)),
    ("loss_ratio", ("loss ratio", "claims ratio"), "percent", "duration", (Profile.GENERAL_INSURER,)),
    ("expense_ratio", ("expense ratio",), "percent", "duration", (Profile.GENERAL_INSURER,)),
    ("fee_revenue", ("fee revenue", "management fees"), "INR_crore", "duration", (Profile.ASSET_MANAGER, Profile.EXCHANGE)),
    ("revenue", ("revenue from operations", "total revenue", "total revenue from operations"), "INR_crore", "duration", COMMON),
    ("net_profit", ("net profit", "profit after tax", "profit for the period", "total profit (loss) for period"), "INR_crore", "duration", COMMON),
    ("capital_adequacy", ("capital adequacy ratio", "CRAR"), "percent", "stock", (Profile.BANK, Profile.NBFC)),
):
    METRICS[key] = MetricDefinition(key, aliases, unit, kind, profiles, "issuer financial disclosure")


def metrics_for_profile(profile: Profile) -> list[MetricDefinition]:
    return [metric for metric in METRICS.values() if profile in metric.profiles]


def resolve_metric(text: str) -> MetricDefinition | None:
    lowered = text.lower()
    for metric in METRICS.values():
        if lowered == metric.key or any(alias.lower() in lowered for alias in metric.aliases):
            return metric
    return None
