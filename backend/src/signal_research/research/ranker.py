from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchScore:
    materiality: int
    evidence_availability: int
    temporal_coherence: int
    additional_insight: int
    contradiction_penalty: int = 0
    comparability_penalty: int = 0

    @property
    def total(self) -> int:
        return self.materiality + self.evidence_availability + self.temporal_coherence + self.additional_insight - self.contradiction_penalty - self.comparability_penalty


def rank_score(score: ResearchScore) -> int:
    """Use only for research allocation, never as a truth probability."""
    return score.total
