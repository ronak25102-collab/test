from __future__ import annotations

from dataclasses import dataclass

from signal_research.domain.schemas import Passage


@dataclass(frozen=True)
class PassageHit:
    passage: Passage
    score: int


def search_passages(passages: list[Passage], terms: list[str], limit: int = 10) -> list[PassageHit]:
    lowered = [term.lower() for term in terms]
    ranked = []
    for passage in passages:
        text = passage.text.lower()
        score = sum(text.count(term) for term in lowered)
        if score:
            ranked.append(PassageHit(passage, score))
    return sorted(ranked, key=lambda hit: hit.score, reverse=True)[:limit]
