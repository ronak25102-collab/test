from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RunContext:
    run_id: str
    cutoff: str
    mode: str
    budget: dict[str, Any]


@dataclass(frozen=True)
class StageResult:
    artifacts: list[str] = field(default_factory=list)
    events: list[str] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    next_state: str | None = None
