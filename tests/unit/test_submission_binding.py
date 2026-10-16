from types import SimpleNamespace

from pydantic import HttpUrl
from signal_research.research.identity import presentation_issuer_identity
from signal_research.research.live import LiveResearch
from signal_research.settings import Settings


def test_shared_portal_presentation_needs_both_filename_and_frontmatter_owner():
    company = SimpleNamespace(legal_name='Quartz Finance Limited', aliases=[])
    text = 'Q1 Investor Presentation\n30 July 2026\nContents\nExecutive summary – Quartz Finance Limited overview'
    assert presentation_issuer_identity(text, 'https://group.example/quartz-finance-q1-results.pdf', company)
    assert presentation_issuer_identity(text, HttpUrl('https://group.example/quartz-finance-q1-results.pdf'), company)
    assert not presentation_issuer_identity(text, 'https://group.example/parent-results.pdf', company)
    assert not presentation_issuer_identity('Investor Presentation', 'https://group.example/quartz-finance.pdf', company)
    assert not presentation_issuer_identity('Different Finance Limited\n' + text,
        'https://group.example/quartz-finance.pdf', company)
    assert not presentation_issuer_identity(text.replace('Investor Presentation', 'Annual Report'),
        'https://group.example/quartz-finance.pdf', company)


def test_peer_extraction_preserves_final_review_not_entire_discovery_window():
    research = LiveResearch.__new__(LiveResearch)
    research.settings = Settings(max_run_seconds=600)
    research.is_deep = True
    research.peer_mode = False
    main_reserve = research.analysis_reserve()
    research.peer_mode = True
    assert 0 < research.analysis_reserve() < main_reserve
    assert research.analysis_reserve() == 80


def test_reasoning_reserve_tracks_stage_caps_without_exceeding_total_fraction():
    from types import SimpleNamespace

    from signal_research.research.live import LiveResearch
    from signal_research.settings import Settings
    settings = Settings(max_run_seconds=900, stage_request_seconds={
        'hypothesizing':90, 'extracting':90, 'normalizing':120,
        'challenging':90, 'composing':120, 'verifying':120})
    research = SimpleNamespace(settings=settings, is_deep=True, peer_mode=False)
    assert LiveResearch.analysis_reserve(research) == 585
    settings.stage_request_seconds = dict.fromkeys(settings.stage_request_seconds, 20)
    assert LiveResearch.analysis_reserve(research) == 120


def test_peer_document_allowance_scales_with_total_cap():
    from types import SimpleNamespace

    from signal_research.research.live import LiveResearch
    for total, expected in [(30,6), (12,4), (3,1), (1,0)]:
        research = SimpleNamespace(budget=SimpleNamespace(max_fetch_documents=total))
        assert LiveResearch.peer_document_reserve(research) == expected
