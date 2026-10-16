"""Schema-driven Track A research angles selected by routed company type."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass


@dataclass(frozen=True)
class Angle:
    key: str
    profiles: tuple[str, ...]
    groups: tuple[tuple[str, ...], ...]
    question: str


ANGLES = (
    Angle('growth_quality', ('bank', 'nbfc', 'housing_finance'), (('gross_advances', 'net_advances', 'aum', 'on_book_loans'), ('gnpa', 'nnpa', 'stage2_ratio', 'stage3_ratio', 'credit_cost')), 'Does growth diverge from asset quality after controlling for scope and structural breaks?'),
    Angle('funding_mix', ('bank',), (('deposits',), ('borrowings', 'gross_advances', 'net_advances')), 'Is funding-mix recovery different from loan growth or its pre-event level?'),
    Angle('funder_dependency', ('bank', 'nbfc', 'housing_finance', 'diversified'), (('borrowings', 'aum', 'on_book_loans'), ('bank_borrowings', 'bond_borrowings', 'co_lending_aum')), 'Is growth disproportionately dependent on a funding source or co-lender?'),
    Angle('customer_shift', ('bank', 'nbfc', 'housing_finance'), (('aum', 'gross_advances', 'net_advances', 'deposits'), ('casa_ratio', 'segment_profit', 'segment_revenue', 'funding_cost')), 'Does a multi-year customer or product mix shift explain the economics?'),
    Angle('insurance_distribution', ('life_insurer',), (('ape', 'vnb', 'new_business_premium'), ('persistency_13m', 'persistency_61m', 'renewal_premium', 'vnb_margin')), 'Does new-business growth conceal a change in customer retention or distribution economics?'),
    Angle('underwriting_mix', ('general_insurer',), (('gross_written_premium', 'earned_premium'), ('combined_ratio', 'loss_ratio', 'expense_ratio')), 'Does premium growth diverge from underwriting quality or product mix?'),
    Angle('flow_fee_mix', ('asset_manager',), (('aum', 'average_aum', 'net_flows'), ('fee_revenue', 'net_profit', 'revenue')), 'Does asset growth conceal a shift in flows, customer mix or realised fee yield?'),
    Angle('segment_dependency', ('diversified', 'exchange'), (('segment_revenue', 'transaction_revenue', 'revenue'), ('segment_profit', 'net_profit', 'trading_turnover')), 'Is headline growth dependent on one segment or revenue source?'),
)


def route_angles(company, facts, calculations, source_texts=(), limit=3):
    profiles = {p.value for p in company.business_profiles}
    if 'nbfc' in profiles and 'housing finance' in company.legal_name.casefold():
        profiles.add('housing_finance')
    available = {f.metric_key for f in facts}
    def score(angle):
        coverage = sum(bool(available & set(group)) for group in angle.groups)
        ids = {f.id for f in facts if any(f.metric_key in group for group in angle.groups)}
        arithmetic = sum(set(c.input_fact_ids) <= ids for c in calculations)
        narrative = any(angle.key.replace('_', ' ') in text.casefold() for text in source_texts)
        return {'key': angle.key, 'question': angle.question, 'metrics': sorted(set().union(*map(set, angle.groups))),
                'coverage_groups': coverage, 'required_groups': len(angle.groups),
                'score': coverage * 4 + min(arithmetic, 3) - int(narrative),
                'management_narrative_penalty': int(narrative),
                'missing_groups': [list(group) for group in angle.groups if not available & set(group)]}
    eligible = [a for a in ANGLES if profiles & set(a.profiles)]
    with ThreadPoolExecutor(max_workers=3) as pool:
        ranked = list(pool.map(score, eligible))
    return sorted(ranked, key=lambda a: a['score'], reverse=True)[:limit]
