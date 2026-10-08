from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChallengeResult:
    strongest_alternative: str
    disconfirming_predictions: tuple[str, ...]
    query: str
    attempted: bool
    summary: str
    unresolved: bool


def challenge_synthetic() -> ChallengeResult:
    return ChallengeResult(
        strongest_alternative="An acquisition, reclassification or deposit-composition shift could explain the growth gap without funding stress.",
        disconfirming_predictions=("a disclosed scope change explains the full movement", "later comparable periods reverse the gap"),
        query="Synthetic Bank acquisition reclassification deposit composition funding cost",
        attempted=True,
        summary="The independent context source was searched and states that a growth gap alone does not establish funding stress; composition and cost evidence remain needed.",
        unresolved=True,
    )
