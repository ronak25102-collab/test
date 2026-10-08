from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID


@dataclass(frozen=True)
class Hypothesis:
    statement: str
    observation_ids: tuple[UUID, ...]
    mechanism: str
    alternative_explanations: tuple[str, ...]
    supporting_predictions: tuple[str, ...]
    contradicting_predictions: tuple[str, ...]
    evidence_needed: tuple[str, ...]
    research_score: dict[str, int] = field(default_factory=dict)
    status: str = "candidate"


def synthetic_hypotheses() -> list[Hypothesis]:
    return [
        Hypothesis(
            statement="Loan growth is running ahead of deposit growth, creating a funding-growth observation.",
            observation_ids=(), mechanism="advances and deposits changed at different rates",
            alternative_explanations=("an acquisition or scope change created the gap", "deposit composition or borrowing mix changed"),
            supporting_predictions=("the gap persists in comparable periods", "funding mix or cost disclosures add mechanism evidence"),
            contradicting_predictions=("a restatement or acquisition explains the entire movement", "the gap reverses in the next comparable disclosure"),
            evidence_needed=("deposit composition", "borrowing mix", "corporate-action disclosure"),
            research_score={"materiality": 3, "availability": 4, "temporal_coherence": 3, "additional_insight": 3},
        ),
        Hypothesis(
            statement="The observed balance-sheet change is primarily a reporting-scope effect.",
            observation_ids=(), mechanism="scope or definition changed between periods",
            alternative_explanations=("organic loan growth",),
            supporting_predictions=("a disclosed reclassification or acquisition is present",),
            contradicting_predictions=("the issuer reports a consistent scope and definition",),
            evidence_needed=("accounting-policy and corporate-action disclosures",),
            research_score={"materiality": 2, "availability": 3, "temporal_coherence": 2, "additional_insight": 2},
        ),
    ]
