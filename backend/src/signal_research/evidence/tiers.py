"""Explicit live publication tiers. Strength never substitutes for numerical/semantic gates."""
from signal_research.domain.enums import EvidenceStrength


def evidence_tier(*, origin_families, non_issuer, peer_comparison_done, unresolved_break,
                  counterargument_searched, counterargument_addressed, issuer_only_facts, limitations_disclosed=True):
    families = sorted(set(origin_families))
    checks = {'three_independent_origins': len(families) >= 3, 'non_issuer_support': non_issuer,
              'peer_comparison_verified': peer_comparison_done, 'no_unresolved_structural_break': not unresolved_break,
              'counterargument_searched': counterargument_searched, 'counterargument_addressed': counterargument_addressed,
              'two_origins_or_peer_comparison': len(families) >= 2 or peer_comparison_done,
              'limitations_disclosed': limitations_disclosed}
    strong = all(checks[k] for k in ('three_independent_origins', 'non_issuer_support', 'peer_comparison_verified',
                 'no_unresolved_structural_break', 'counterargument_searched', 'counterargument_addressed'))
    moderate = checks['two_origins_or_peer_comparison'] and counterargument_searched and counterargument_addressed and limitations_disclosed
    strength = EvidenceStrength.STRONG if strong else EvidenceStrength.MODERATE if moderate else EvidenceStrength.WEAK
    caps = []
    if issuer_only_facts:
        caps.append('All verified issuer-company figures originate with the issuer: maximum Moderate.')
        if strength == EvidenceStrength.STRONG:
            strength = EvidenceStrength.MODERATE
    if not peer_comparison_done:
        strength = EvidenceStrength.WEAK
        caps.append('Same-period figures from at least two peers could not be verified: maximum Weak.')
    return strength, {'rules': checks, 'origin_families': families, 'caps': caps,
                      'rating': strength.value, 'numerical_gates': 'passed',
                      'note': 'Tier describes corroboration and unresolved alternatives, not investment advice or proof of causality.'}
