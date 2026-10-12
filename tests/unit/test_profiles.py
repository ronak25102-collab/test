import pytest
from signal_research.domain.enums import Profile
from signal_research.research.planner import initial_plan
from signal_research.research.profiles import profile_for


@pytest.mark.parametrize("profile", list(Profile))
def test_every_profile_loads_and_builds_a_research_plan(profile):
    config = profile_for(profile)
    plan = initial_plan("Example Financial Company", profile, "EXAMPLE", "2026-10-11")

    assert config.profile == profile
    assert config.required_metrics
    assert len(plan) == len(config.starter_questions) == 2
    assert [task.question for task in plan] == list(config.starter_questions)
    assert all(task.question.endswith("?") for task in plan)
    assert all("Example Financial Company" in task.query for task in plan)
