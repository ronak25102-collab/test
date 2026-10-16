from datetime import date
from types import SimpleNamespace
from uuid import uuid4

from signal_research.domain.enums import Scope
from signal_research.research.live import LiveResearch
from signal_research.research.report_builder import build_synthetic_report


def test_compact_planning_retains_verified_data_and_review_restores_original_spans(store):
    company = store.search_companies('HDFCBANK')[0]
    report = build_synthetic_report(uuid4(), company, date(2026, 10, 15))
    research = LiveResearch.__new__(LiveResearch)
    research.company, research.cutoff = company, report.cutoff
    research.documents, research.passages = report.documents, report.passages
    research.facts, research.calculations = list(report.facts), report.calculations
    research.structural_breaks = []
    research.peer_benchmark = {}
    unused = report.facts[0].model_copy(update={'id': uuid4(), 'scope': Scope.STANDALONE
        if report.facts[0].scope == Scope.CONSOLIDATED else Scope.CONSOLIDATED})
    research.facts.append(unused)
    plan = research.payload(compact=True)
    assert len(plan['facts']) == len(research.facts)
    assert 'original numeric spans are omitted' in plan['coverage_note']
    assert not any(p['source_role'] == 'verified_figure_span' for p in plan['passages'])
    candidate = SimpleNamespace(fact_ids=[f.id for f in report.facts],
                                calculation_ids=[c.id for c in report.calculations],
                                statement='Funding mix and balance expansion', mechanism='')
    review = research.payload(candidate)
    assert unused.id not in {f['id'] for f in review['facts']}
    original = {p.id: p.text for p in report.passages}
    figures = [p for p in review['passages'] if p['source_role'] == 'verified_figure_span']
    assert figures
    assert all(p['text'] == original[p['id']] for p in figures)
    assert {p['id'] for p in figures} >= {f.passage_id for f in report.facts}
