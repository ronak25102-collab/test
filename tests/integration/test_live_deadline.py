from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError
from signal_research.domain.enums import RunMode
from signal_research.research.readiness import live_readiness
from signal_research.research.report_builder import build_abstention
from signal_research.settings import Settings
from signal_research.worker.machine import ResearchMachine


@pytest.mark.parametrize('mode,ceiling,expected', [
    (RunMode.LIVE, 900, 600), (RunMode.LIVE, 120, 120), (RunMode.DEEP, 900, 900)])
def test_worker_deadline_matches_public_live_ceiling_and_keeps_lower_limits(store, tmp_path, monkeypatch, mode, ceiling, expected):
    settings = Settings(data_dir=tmp_path, allow_unknown_cost=True, max_run_seconds=ceiling,
                        demo_target_seconds=600, tavily_api_key='test-only', openai_api_key='test-only',
                        openai_model_extract='test', openai_model_research='test')
    company = store.search_companies('HDFCBANK')[0]
    rid = store.create_run(company, date(2026, 10, 8), mode)
    store.lease_next('deadline-check')
    observed = []
    def process(self, run_id, cutoff, company, plan, budget):
        started = store.get_summary(run_id).started_at.replace(tzinfo=UTC)
        observed.append((budget.deadline - started).total_seconds())
        return build_abstention(run_id, company, cutoff, mode=mode.value)
    monkeypatch.setattr(ResearchMachine, '_process_live', process)
    ResearchMachine(store, settings).process(rid)
    assert observed == [expected]
    assert store.get_summary(rid).status.value == 'completed'
    assert live_readiness(settings)['max_run_seconds'] == min(ceiling, 600)


def test_new_defaults_allow_ten_minutes_and_resume_never_extends_saved_deadline(store, tmp_path, monkeypatch):
    settings = Settings(data_dir=tmp_path, allow_unknown_cost=True, tavily_api_key='test-only', openai_api_key='test-only',
                        openai_model_extract='test', openai_model_research='test')
    assert settings.max_run_seconds == settings.demo_target_seconds == 600
    with pytest.raises(ValidationError):
        Settings(demo_target_seconds=601)
    company = store.search_companies('HDFCBANK')[0]
    rid = store.create_run(company, date(2026, 10, 8), RunMode.LIVE)
    original = datetime.now(UTC) + timedelta(seconds=300)
    store.update_run(rid, budget={'deadline': original.isoformat()})
    store.lease_next('resume-deadline-check')
    def process(self, run_id, cutoff, company, plan, budget):
        assert budget.deadline == original
        return build_abstention(run_id, company, cutoff, mode='live')
    monkeypatch.setattr(ResearchMachine, '_process_live', process)
    ResearchMachine(store, settings).process(rid)
    assert store.get_summary(rid).status.value == 'completed'
    assert store.get_summary(rid).budget['deadline'] == original.isoformat()
