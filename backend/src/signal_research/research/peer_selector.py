from __future__ import annotations

import re
from dataclasses import dataclass

from signal_research.domain.enums import Profile
from signal_research.domain.schemas import Company


@dataclass(frozen=True)
class PeerSelection:
    peers: tuple[Company, ...]
    reasons: tuple[str, ...]


def select_peers(target: Company, candidates: list[Company], profile: Profile, limit: int = 3) -> PeerSelection:
    def legacy_housing_false_positive(company):
        # Old directory imports treated every housing developer as a lender.
        # A housing label alone cannot establish a financial peer, including
        # in existing caches created before the inference correction.
        name = company.legal_name.lower()
        return profile == Profile.NBFC and 'housing' in name and not re.search(r'finance|financial|lending|nbfc', name)
    eligible = [candidate for candidate in candidates if candidate.id != target.id and "SYNTHBANK" not in candidate.symbols
                and profile in candidate.business_profiles and not legacy_housing_false_positive(candidate)]
    def specialization(company):
        # Legal-name classifications are generic directory attributes, never
        # a hand-picked ticker list. Prefer comparable business models first.
        return next((label for label in ('small finance', 'payments', 'regional rural', 'housing finance')
                     if re.search(r'\b' + label + r'\b', company.legal_name, re.I)), 'general')
    peers = tuple(sorted(eligible, key=lambda c: (
        specialization(c) != specialization(target), not bool(c.verified_ir_domains), c.legal_name))[:limit])
    return PeerSelection(peers, tuple(f"same routed profile: {profile.value}; business model: {specialization(c)}" for c in peers))
