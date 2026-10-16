from threading import Barrier

from signal_research.research.agents import run_research_agents


def test_runtime_agents_overlap_keep_result_order_and_report_progress():
    barrier = Barrier(3)
    events = []
    def work(index):
        barrier.wait(timeout=3)
        return index
    results = run_research_agents([(str(i), lambda i=i: work(i)) for i in range(3)],
                                 max_workers=3, emit=lambda *args: events.append(args))
    assert [r.value for r in results] == [0, 1, 2]
    assert len([e for e in events if e[1] == 'started']) == 3
    assert len([e for e in events if e[1] == 'completed']) == 3


def test_agent_failure_does_not_discard_another_agents_result_or_expose_error_text():
    events = []
    def fail():
        raise TimeoutError('sensitive provider text')
    results = run_research_agents([('issuer', lambda: 12), ('peer', fail)], max_workers=2,
                                 emit=lambda *args: events.append(args))
    assert results[0].value == 12 and results[0].error is None
    assert isinstance(results[1].error, TimeoutError)
    assert events[-1][1] in {'completed', 'failed'}
    assert any(e[0] == 'peer' and e[1] == 'failed' and e[3] == 'TimeoutError' for e in events)
    assert 'sensitive' not in str(events)
    assert run_research_agents([], max_workers=3) == []
