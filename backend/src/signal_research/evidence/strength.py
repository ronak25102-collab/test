from __future__ import annotations

from signal_research.domain.enums import EvidenceStrength


def label_strength(*, independent_origins: int, unresolved_alternative: bool, central_calculations_verified: bool) -> tuple[EvidenceStrength, str]:
    if independent_origins >= 2 and central_calculations_verified and not unresolved_alternative:
        return EvidenceStrength.STRONG, "Primary facts, reproducible calculations and independent relevant origins passed the challenge without a material unresolved alternative."
    if independent_origins >= 2 and central_calculations_verified:
        return EvidenceStrength.MODERATE, "Primary facts and calculations are verified across relevant origins, but a plausible alternative mechanism remains."
    return EvidenceStrength.WEAK, "The evidence is incomplete or fragile; this lead should not be treated as a completed primary discovery."
