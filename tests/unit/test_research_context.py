from uuid import uuid4

from signal_research.domain.schemas import Passage
from signal_research.research.context import diverse_context, exact_excerpt


def test_late_funding_evidence_is_visible_with_exact_offsets():
    text = ('Navigation and unrelated corporate announcements. ' * 90 +
            'Deposit funding became more expensive as wholesale borrowings increased. ' * 10)
    excerpt = exact_excerpt(text, [], 'deposit funding borrowings', limit=800)
    start = excerpt['source_character_offset']
    assert excerpt['text'] == text[start:start + 800]
    assert 'wholesale borrowings' in excerpt['text']
    assert excerpt['excerpt_only']


def test_numeric_anchors_take_priority_over_an_early_cover_name():
    text = 'Example Bank\n' + 'Unrelated text. ' * 200 + 'Deposits 123456 and borrowings 98765'
    excerpt = exact_excerpt(text, ['Example Bank', '123456', '98765'], limit=500)
    assert '123456' in excerpt['text'] and '98765' in excerpt['text']
    assert excerpt['omitted_anchors'] == ['Example Bank']


def test_origin_diversity_prevents_copies_crowding_out_original_evidence():
    from types import SimpleNamespace

    documents, passages = {}, []
    for origin in ['wire-copy', 'wire-copy', 'rating-origin', 'regulator']:
        identifier = uuid4()
        documents[identifier] = SimpleNamespace(origin_family_id=origin)
        passages.extend(Passage(id=uuid4(), document_id=identifier,
                                text='Example Bank deposit funding review') for _ in range(3))
    selected = diverse_context(passages, documents, ['Example Bank'], 'deposit funding')
    assert {documents[p.document_id].origin_family_id for p in selected} == {
        'wire-copy', 'rating-origin', 'regulator'}
    assert len(selected) == 4
