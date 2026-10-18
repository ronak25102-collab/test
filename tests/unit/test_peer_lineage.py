"""A peer comparison claim links the verified peer passages it relies on, and nothing else."""
from types import SimpleNamespace
from uuid import uuid4

from signal_research.research.live import LiveResearch


def research_with_peers(status='verified'):
    issuer_fact = SimpleNamespace(id=uuid4(), metric_key='borrowings', scope=SimpleNamespace(value='consolidated'))
    peer_passage, other_passage, unattached = uuid4(), uuid4(), uuid4()
    research = LiveResearch.__new__(LiveResearch)
    research.facts, research.calculations = [issuer_fact], []
    research.passages = [SimpleNamespace(id=peer_passage), SimpleNamespace(id=other_passage)]
    research.peer_benchmark = {'status': status, 'sources': [{'facts': [
        {'metric_key': 'borrowings', 'scope': 'consolidated', 'passage_id': str(peer_passage)},
        {'metric_key': 'borrowings', 'scope': 'standalone', 'passage_id': str(other_passage)},
        {'metric_key': 'borrowings', 'scope': 'consolidated', 'passage_id': str(unattached)},
        {'metric_key': 'gnpa', 'scope': 'consolidated', 'passage_id': str(other_passage)}]}]}
    return research, issuer_fact, peer_passage


def statement(text, fact):
    return SimpleNamespace(text=text, fact_ids=[fact.id], calculation_ids=[], passage_ids=[])


def test_peer_claim_links_only_matching_attached_peer_passages():
    research, fact, peer_passage = research_with_peers()
    linked = research.complete_peer_lineage(statement('Borrowings fell while peers rose.', fact))
    # Same metric and scope, already citable: linked. Other scope, other metric, unattached: not.
    assert linked == [peer_passage]


def test_no_peer_wording_or_unverified_benchmark_adds_nothing():
    research, fact, _ = research_with_peers()
    assert research.complete_peer_lineage(statement('Borrowings fell 5.63%.', fact)) == []
    assert research.complete_peer_lineage(statement('Sector deposit growth slowed.', fact)) == []
    research, fact, _ = research_with_peers(status='inconclusive')
    assert research.complete_peer_lineage(statement('Borrowings fell while peers rose.', fact)) == []
