from __future__ import annotations

from enum import StrEnum


class Novelty(StrEnum):
    SIMPLE_RESTATEMENT = "simple_restatement"
    ADDITIONAL_SYNTHESIS = "additional_supported_synthesis"
    ALREADY_COVERED = "already_covered"
    UNKNOWN = "novelty_unknown"


def classify_novelty(headline: str, contemporaneous_titles: list[str]) -> Novelty:
    normalized = headline.lower()
    if any(normalized in title.lower() or title.lower() in normalized for title in contemporaneous_titles):
        return Novelty.ALREADY_COVERED
    if not contemporaneous_titles:
        return Novelty.UNKNOWN
    return Novelty.ADDITIONAL_SYNTHESIS
