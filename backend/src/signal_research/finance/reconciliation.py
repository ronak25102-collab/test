from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Reconciliation:
    expected: Decimal
    reported: Decimal
    residual: Decimal
    tolerance: Decimal
    reconciled: bool
    explanation: str


def reconcile(expected: Decimal, reported: Decimal, tolerance: Decimal = Decimal("0.5")) -> Reconciliation:
    residual = reported - expected
    return Reconciliation(expected, reported, residual, tolerance, abs(residual) <= tolerance, "Residual is within source-rounding tolerance" if abs(residual) <= tolerance else "Residual requires disclosed other adjustments or a scope review")
