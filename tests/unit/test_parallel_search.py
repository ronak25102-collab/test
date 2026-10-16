from threading import Barrier
from types import SimpleNamespace

from signal_research.research.live import LiveResearch


def test_independent_searches_overlap_but_keep_query_order():
    barrier = Barrier(3)
    def search(query, domains):
        barrier.wait(timeout=3)
        return [query, domains]
    research = SimpleNamespace(search=search)
    assert LiveResearch.search_many(research, [("issuer", ["issuer.example"]), ("regulator", None), ("peer", ["peer.example"])]) == [
        ["issuer", ["issuer.example"]], ["regulator", None], ["peer", ["peer.example"]]]


def test_empty_search_batch_makes_no_requests():
    def unexpected(*args):
        raise AssertionError("No external work should happen")
    assert LiveResearch.search_many(SimpleNamespace(search=unexpected), []) == []
