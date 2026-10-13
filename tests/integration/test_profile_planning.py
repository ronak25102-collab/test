from datetime import date
from pathlib import Path

import pytest
import yaml
from signal_research.db.models import CompanyModel
from signal_research.domain.enums import Profile, RunMode, RunStatus
from signal_research.finance.calculations import FORMULAS
from signal_research.research import profiles
from signal_research.research.planner import initial_plan
from signal_research.research.profiles import available_metric_keys, profile_for
from signal_research.research.report_builder import build_abstention
from signal_research.worker.machine import ResearchMachine


@pytest.mark.parametrize("profile", list(Profile))
def test_every_bundled_profile_reaches_live_research(store, settings, monkeypatch, profile):
    # Read the actual packaged YAML: built-in fallback values must not hide a
    # missing or malformed profile file, or corrupt question punctuation.
    path = Path(profiles.__file__).parents[1] / "profiles" / f"{profile.value}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    config = profile_for(profile)
    assert data["profile"] == profile.value
    assert config.starter_questions == tuple(data["starter_questions"])
    assert len(config.starter_questions) >= 2
    assert all(isinstance(q, str) and q.endswith("?") for q in config.starter_questions)
    assert set(config.required_metrics) <= set(available_metric_keys(profile))
    assert set(config.calculation_ids) <= FORMULAS.keys()

    company = store.search_companies("BAJFINANCE")[0]
    with store.session_factory() as session:
        row = session.get(CompanyModel, str(company.id))
        row.business_profiles = [profile.value]
        session.commit()
    company = store.get_company(company.id)
    cutoff = date(2026, 10, 11)
    expected = initial_plan(company.legal_name, profile, company.symbols[0], str(cutoff))
    assert [task.question for task in expected] == list(config.starter_questions)
    assert all(company.legal_name in task.query and str(cutoff) in task.query for task in expected)

    reached_live = []

    def without_provider_requests(machine, run_id, as_of, resolved_company, plan, budget):
        assert plan == expected
        assert machine.store.load_checkpoint(run_id, "planning") is not None
        reached_live.append(run_id)
        return build_abstention(
            run_id, resolved_company, as_of, [], [], [], ["Offline planning test"], mode="live"
        )

    settings = settings.model_copy(update={
        "tavily_api_key": "test-only",
        "openai_api_key": "test-only",
        "openai_model_research": "test-research",
        "openai_model_extract": "test-extract",
        "allow_unknown_cost": True,
    })
    monkeypatch.setattr(ResearchMachine, "_process_live", without_provider_requests)
    run_id = store.create_run(company, cutoff, RunMode.LIVE)
    assert store.lease_next("profile-planning-test") == run_id
    ResearchMachine(store, settings).process(run_id)
    assert reached_live == [run_id]
    assert store.get_summary(run_id).status == RunStatus.COMPLETED
    assert store.get_summary(run_id).budget["search_calls"] == 0
    assert store.get_summary(run_id).budget["model_calls"] == 0
