from dataclasses import dataclass


@dataclass(frozen=True)
class HypothesisDisposition:
    status: str
    reason: str
    supporting_evidence_ids: tuple[str, ...] = ()
    opposing_evidence_ids: tuple[str, ...] = ()
