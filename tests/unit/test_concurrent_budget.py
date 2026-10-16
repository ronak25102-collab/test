from concurrent.futures import ThreadPoolExecutor

from signal_research.domain.errors import BudgetExceeded
from signal_research.worker.budgets import Budget


def test_parallel_reservations_cannot_overrun_the_shared_budget():
    budget = Budget(5, 5, 5, 0)
    def reserve(_):
        try:
            budget.reserve('search_calls')
            return 1
        except BudgetExceeded:
            return 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(reserve, range(40))) == 5
    assert budget.snapshot()['search_calls'] == 5
