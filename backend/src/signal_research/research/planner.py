from __future__ import annotations

from dataclasses import dataclass

from signal_research.domain.enums import Profile

from .profiles import profile_for


@dataclass(frozen=True)
class ResearchTask:
    question: str
    query: str
    reason: str
    required_metrics: tuple[str, ...]
    priority: int


def initial_plan(company_name: str, profile: Profile, symbol: str, as_of: str) -> list[ResearchTask]:
    config = profile_for(profile)
    tasks = []
    for priority, question in enumerate(config.starter_questions, 1):
        tasks.append(ResearchTask(question, f'"{company_name}" {symbol} {question} results {as_of}', "profile starter question", config.required_metrics, priority))
    return tasks[:6]
