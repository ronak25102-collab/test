"""Keep supported significance; at most one existing coverage note can replace context."""
from signal_research.domain.enums import ClaimKind
from signal_research.research.claim_numbers import supported_numbers
from signal_research.research.numeric_claims import (
    complete_calculation_lineage,
    supported_percentages,
)


def coverage_repair(draft, facts, calculations):
    by_fact, by_calc = {f.id:f for f in facts}, {c.id:c for c in calculations}
    def supported(statement):
        if not(statement.fact_ids or statement.calculation_ids):
            return False
        ids = complete_calculation_lineage(statement.text, statement.fact_ids, statement.calculation_ids, calculations)
        if not set(statement.fact_ids) <= by_fact.keys() or not set(ids) <= by_calc.keys():
            return False
        fs, cs = [by_fact[i] for i in statement.fact_ids], [by_calc[i] for i in ids]
        return supported_numbers(statement.text, fs, cs) and supported_percentages(statement.text, fs, cs)
    if not all(supported(s) for s in (draft.headline, draft.timeline_analysis, draft.counterargument)):
        return None
    rejected = [i for i, statement in enumerate(draft.why_it_matters) if not supported(statement)]
    if not rejected:
        return None
    kept = [s for i,s in enumerate(draft.why_it_matters) if i not in rejected]
    if len(kept) >= 3:
        return draft.model_copy(update={'why_it_matters':kept})
    if len(kept) != 2:
        return None  # Cannot fill a missing research story with boilerplate.
    calc = next((c for c in calculations if c.id in draft.headline.calculation_ids and c.available
                 and c.limitations and set(c.input_fact_ids) <= by_fact.keys() and len(c.input_fact_ids) <= 8), None)
    if calc is None:
        return None
    from signal_research.research.live import Statement
    replacement = Statement(text=' '.join(calc.limitations)[:600], kind=ClaimKind.DERIVED,
        fact_ids=list(dict.fromkeys(calc.input_fact_ids)), calculation_ids=[calc.id], passage_ids=[])
    if not supported(replacement) or any(s.text == replacement.text for s in draft.why_it_matters):
        return None
    items = [replacement if i==rejected[0] else statement for i,statement in enumerate(draft.why_it_matters)
             if i not in rejected or i==rejected[0]]
    return draft.model_copy(update={'why_it_matters':items})
