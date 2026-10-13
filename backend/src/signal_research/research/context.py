"""Select exact evidence excerpts for a specific research question."""
from __future__ import annotations

import re

STOP_WORDS = {"the", "and", "for", "with", "from", "that", "this", "into", "than",
              "may", "can", "could", "would", "have", "has", "been", "were", "are"}


def topic_terms(question: str) -> set[str]:
    return {word for word in re.findall(r"[a-z][a-z-]{2,}", question.lower())
            if word not in STOP_WORDS}


def relevance(text: str, identities: list[str], question: str = "") -> tuple[int, int]:
    lowered = text.lower()
    issuer = any(re.search(r"\b" + re.escape(name.lower()) + r"\b", lowered)
                 for name in identities if name)
    matched = sum(bool(re.search(r"\b" + re.escape(term) + r"\b", lowered))
                  for term in topic_terms(question))
    return int(issuer), matched


def exact_excerpt(text: str, anchors: list[str], question: str = "", limit: int = 2000) -> dict:
    """Return an exact contiguous source span, with original character offsets."""
    if len(text) <= limit:
        return {"text": text, "source_character_offset": 0, "excerpt_only": False,
                "omitted_anchors": []}
    lowered = text.lower()
    positions = [(anchor, lowered.find(anchor.lower())) for anchor in anchors if anchor]
    positions = [(anchor, index) for anchor, index in positions if index >= 0]
    if positions:
        numeric = [(anchor, index) for anchor, index in positions if re.search(r"\d", anchor)]
        start = max(0, min(index for _, index in (numeric or positions)) - 400)
    else:
        terms = topic_terms(question)
        windows = range(0, len(text), max(1, limit // 2))
        start = max(windows, key=lambda offset: sum(
            len(re.findall(r"\b" + re.escape(term) + r"\b", lowered[offset:offset + limit]))
            for term in terms)) if terms else 0
    start = min(start, len(text) - limit)
    return {"text": text[start:start + limit], "source_character_offset": start,
            "excerpt_only": True,
            "omitted_anchors": [anchor for anchor, index in positions
                                if index < start or index + len(anchor) > start + limit]}


def diverse_context(passages, documents, identities, question="", limit=4):
    """Represent original origins before spending slots on duplicate pages."""
    ranked = sorted(passages, key=lambda p: relevance(p.text, identities, question), reverse=True)
    selected, document_counts, origin_counts = [], {}, {}
    for per_origin in (1, 2):
        for passage in ranked:
            if passage in selected:
                continue
            origin = documents[passage.document_id].origin_family_id
            if origin_counts.get(origin, 0) >= per_origin or document_counts.get(passage.document_id, 0) >= 2:
                continue
            selected.append(passage)
            document_counts[passage.document_id] = document_counts.get(passage.document_id, 0) + 1
            origin_counts[origin] = origin_counts.get(origin, 0) + 1
            if len(selected) >= limit:
                return sorted(selected, key=lambda p: relevance(p.text, identities, question), reverse=True)
    return sorted(selected, key=lambda p: relevance(p.text, identities, question), reverse=True)
