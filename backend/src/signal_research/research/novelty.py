from __future__ import annotations

from enum import StrEnum


class Novelty(StrEnum):
    SIMPLE_RESTATEMENT = "simple_restatement"
    ADDITIONAL_SYNTHESIS = "additional_supported_synthesis"
    ALREADY_COVERED = "already_covered"
    UNKNOWN = "novelty_unknown"


def classify_novelty(headline: str, contemporaneous_titles: list[str]) -> Novelty:
    normalized = headline.lower()
    titles = [title.lower().strip() for title in contemporaneous_titles if len(title.split()) >= 6]
    if any(normalized == title or normalized in title or title in normalized for title in titles):
        return Novelty.ALREADY_COVERED
    if not contemporaneous_titles:
        return Novelty.UNKNOWN
    # Different wording proves neither novelty nor additional reasoning.
    # The source-based challenge and independent final review assess synthesis.
    return Novelty.UNKNOWN
