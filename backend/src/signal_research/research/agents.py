"""Bounded runtime research agents. Results are merged only by their coordinator."""
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from time import monotonic
from typing import Any


@dataclass
class AgentResult:
    name: str
    value: Any = None
    error: Exception | None = None
    elapsed_seconds: float = 0


def run_research_agents(tasks: list[tuple[str, Callable]], *, max_workers: int, emit=None):
    """Observe every future, isolate failures, and preserve task order.

    Each task must own its mutable research state and obey the shared run budget.
    A future timeout alone cannot stop a billed request, so request deadlines stay
    inside the existing durable provider adapter rather than being retried here.
    """
    def run(name, work):
        started = monotonic()
        if emit:
            emit(name, 'started', 0, None)
        try:
            result = AgentResult(name, value=work())
        except Exception as exc:
            result = AgentResult(name, error=exc)
        result.elapsed_seconds = round(monotonic() - started, 3)
        if emit:
            emit(name, 'failed' if result.error else 'completed', result.elapsed_seconds,
                 getattr(result.error, 'code', type(result.error).__name__) if result.error else None)
        return result
    if not tasks:
        return []
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, min(max_workers, len(tasks))), thread_name_prefix='beyond-agent') as pool:
        futures = {pool.submit(run, name, work): index for index, (name, work) in enumerate(tasks)}
        for future in as_completed(futures):
            results[futures[future]] = future.result()
    return [results[index] for index in range(len(tasks))]
