"""Business-type research guidance shared by every issuer in that type."""
from signal_research.domain.enums import Profile

CONTEXT_TERMS = {
    Profile.BANK: "deposits advances asset quality funding liquidity",
    Profile.NBFC: "AUM asset quality cost of funds co-lending funding mix",
    Profile.LIFE_INSURER: "VNB APE persistency product mix distribution solvency",
    Profile.GENERAL_INSURER: "underwriting claims reserves combined ratio solvency",
    Profile.EXCHANGE: "transaction fees trading volumes regulation market share",
    Profile.ASSET_MANAGER: "AUM net flows fee yield product mix",
    Profile.DIVERSIFIED: "segment revenue segment profit related party group funding",
}


def extraction_instruction(profile):
    focus = CONTEXT_TERMS[Profile(profile)]
    return (
        f"Extract at most six complete source-backed facts relevant to {focus}. "
        "Prefer comparable periods and preserve each explicitly named business segment; "
        "use segment='all' only for issuer totals. Copy raw cells without converting scale. "
        "Every period_end must match its own column. Stock balances have instant period_type "
        "and null period_start; duration measures need their explicit start and end. "
        "SOLO and GROUP columns distinguish standalone and consolidated reporting only when "
        "the table identifies the target issuer and both column groups. Never relabel net "
        "advances as gross advances, NPA amounts as ratios, or managed AUM as on-book loans. "
        "A rupee symbol means INR; in '000 means thousand rupees; in Crores means INR crore. "
        "Retain the complete source passage with evidence_quote=null. Reject ambiguous "
        "row/column, entity, scope, currency, scale, definitions or dates. Do not infer dates "
        "from FY or quarter labels alone. Omit incomplete facts rather than inventing values. "
        "Return facts=[] when none are complete. missing_metrics may contain only supplied "
        "registered keys, each at most once; give at most one brief note explaining the gap."
    )
