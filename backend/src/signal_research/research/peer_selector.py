from __future__ import annotations

from dataclasses import dataclass

from signal_research.domain.enums import Profile
from signal_research.domain.schemas import Company


@dataclass(frozen=True)
class PeerSelection:
    peers: tuple[Company, ...]
    reasons: tuple[str, ...]


def select_peers(target: Company, candidates: list[Company], profile: Profile, limit: int = 3) -> PeerSelection:
    eligible = [candidate for candidate in candidates if candidate.id != target.id and "SYNTHBANK" not in candidate.symbols and profile in candidate.business_profiles]
    peers = tuple(sorted(eligible, key=lambda c: (not bool(c.verified_ir_domains), c.legal_name))[:limit])
    return PeerSelection(peers, tuple(f"same routed profile: {profile.value}" for _ in peers))
