from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from signal_research.domain.schemas import SourceDocument


@dataclass(frozen=True)
class IndependenceResult:
    origin_families: tuple[str, ...]
    relevant_families: tuple[str, ...]
    eligible: bool
    reason: str


def check_independence(documents: list[SourceDocument], relevant_document_ids: set) -> IndependenceResult:
    families = defaultdict(list)
    for document in documents:
        if document.id in relevant_document_ids and document.cutoff_eligibility == "eligible":
            families[document.origin_family_id].append(document)
    relevant = tuple(sorted(families))
    primary = any(document.document_type.startswith("issuer") for family in families.values() for document in family)
    eligible = len(relevant) >= 2 and primary
    if eligible:
        reason = "two relevant eligible origin families, including a target-company primary source"
    elif not primary:
        reason = "target-company primary source is missing"
    else:
        reason = "fewer than two relevant independent origin families"
    return IndependenceResult(tuple(sorted(families)), relevant, eligible, reason)
