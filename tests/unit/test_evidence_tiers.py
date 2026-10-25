from signal_research.evidence.tiers import evidence_tier


def test_explicit_tiers_and_caps():
    args = dict(origin_families=['issuer:a', 'regulator:r', 'news:n'], non_issuer=True,
                peer_comparison_done=True, unresolved_break=False, counterargument_searched=True,
                counterargument_addressed=True, issuer_only_facts=False)
    assert evidence_tier(**args)[0].value == 'Strong'
    assert evidence_tier(**(args | {'issuer_only_facts': True}))[0].value == 'Moderate'
    assert evidence_tier(**(args | {'peer_comparison_done': False}))[0].value == 'Weak'
    assert evidence_tier(**(args | {'counterargument_addressed': False}))[0].value == 'Weak'
    assert evidence_tier(**(args | {'unresolved_break': True}))[0].value == 'Moderate'
    strength, trace = evidence_tier(**(args | {'origin_families': ['issuer:a', 'issuer:a']}))
    assert strength.value == 'Moderate' and len(trace['origin_families']) == 1


def test_reviewed_arithmetic_can_be_moderate_without_peer_breadth():
    args = dict(origin_families=['issuer:a'], non_issuer=False,
                peer_comparison_done=False, unresolved_break=False,
                counterargument_searched=True, counterargument_addressed=True,
                issuer_only_facts=True, source_verified_arithmetic=True)
    strength, trace = evidence_tier(**args)
    assert strength.value == 'Moderate'
    assert trace['rules']['source_verified_arithmetic']
    assert not trace['rules']['peer_comparison_verified']
    assert any('sector differentiation or causality' in note for note in trace['caps'])
    assert evidence_tier(**(args | {'source_verified_arithmetic': False}))[0].value == 'Weak'
    assert evidence_tier(**(args | {'counterargument_searched': False}))[0].value == 'Weak'
