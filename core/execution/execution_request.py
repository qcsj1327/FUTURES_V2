from __future__ import annotations

from dataclasses import dataclass

from domain.risk import RiskDecision


@dataclass(frozen=True)
class ExecutionRequest:
    risk_decision: RiskDecision
    order_price: float | None = None
