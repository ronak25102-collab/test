from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from signal_research.domain.errors import BudgetExceeded


@dataclass
class Budget:
    max_search_calls: int
    max_fetch_documents: int
    max_model_calls: int
    max_ocr_pages: int
    search_calls: int = 0
    fetch_documents: int = 0
    model_calls: int = 0
    ocr_pages: int = 0
    max_input_tokens: int = 150000
    max_output_tokens: int = 20000
    max_cost_usd: float = 5.0
    input_tokens: int = 0
    output_tokens: int = 0
    reserved_cost_usd: float = 0.0
    deadline: datetime | None = None
    persist: Callable | None = field(default=None, repr=False)

    def check(self) -> None:
        if self.deadline and datetime.now(UTC) >= self.deadline:
            raise BudgetExceeded("run deadline exceeded")

    def remaining_seconds(self) -> float:
        self.check()
        return max(0.1, (self.deadline - datetime.now(UTC)).total_seconds()) if self.deadline else 420.0

    def reserve(self, kind: str, amount: int = 1) -> None:
        self.check()
        current = getattr(self, kind)
        maximum = getattr(self, f"max_{kind}")
        if current + amount > maximum:
            raise BudgetExceeded(f"budget exceeded for {kind}")
        setattr(self, kind, current + amount)
        self._persist()

    def reserve_model(self, input_tokens: int, output_tokens: int, cost: float):
        self.check()
        for kind, amount in (("model_calls", 1), ("input_tokens", input_tokens), ("output_tokens", output_tokens)):
            if getattr(self, kind) + amount > getattr(self, f"max_{kind}"):
                raise BudgetExceeded(f"budget exceeded for {kind}")
        if self.reserved_cost_usd + cost > self.max_cost_usd:
            raise BudgetExceeded("estimated dollar budget exceeded")
        self.model_calls += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.reserved_cost_usd += cost
        self._persist()

    def reserve_search(self, cost: float):
        self.check()
        if self.reserved_cost_usd + cost > self.max_cost_usd:
            raise BudgetExceeded("estimated dollar budget exceeded")
        self.reserve("search_calls")
        self.reserved_cost_usd += cost
        self._persist()

    def release_rejected_model(self, reserved_input, reserved_output, reserved_cost):
        """Release tokens/cost only for an explicit pre-inference credit rejection.

        Keep the attempted model call counted, so failover remains bounded.
        Timeouts, malformed results and rate limits never receive this refund.
        """
        self.input_tokens -= reserved_input
        self.output_tokens -= reserved_output
        self.reserved_cost_usd -= reserved_cost
        self._persist()

    def settle_model(self, reserved_input, reserved_output, actual_input, actual_output, reserved_cost, actual_cost):
        if actual_input > 0 and actual_output > 0:
            self.input_tokens += actual_input - reserved_input
            self.output_tokens += actual_output - reserved_output
            self.reserved_cost_usd += actual_cost - reserved_cost
            self._persist()
            if self.input_tokens > self.max_input_tokens or self.output_tokens > self.max_output_tokens or self.reserved_cost_usd > self.max_cost_usd:
                raise BudgetExceeded("provider usage exceeded its reservation")

    def _persist(self):
        if self.persist:
            self.persist(self.snapshot())

    def snapshot(self) -> dict:
        limits = {key: getattr(self, key) for key in ("max_search_calls", "max_fetch_documents", "max_model_calls", "max_ocr_pages", "max_input_tokens", "max_output_tokens", "max_cost_usd")}
        return {key: getattr(self, key) for key in ("search_calls", "fetch_documents", "model_calls", "ocr_pages", "input_tokens", "output_tokens", "reserved_cost_usd")} | {"deadline": self.deadline.isoformat() if self.deadline else None, "limits": limits, "cost_accounting": "conservative reservations; uncertain calls remain charged"}
