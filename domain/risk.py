from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.enums import Decision, PositionSide, Side, TriggerLifecycle


@dataclass(frozen=True)
class RiskContext:
    reference_price: float | None = None
    volatility: float | None = None
    risk_level: str | None = None
    current_position_qty: float = 0.0
    current_position_side: PositionSide | None = None
    max_position_qty: float | None = None


@dataclass(frozen=True)
class RiskDecision:
    instrument_id: str
    trade_instrument_id: str
    allowed: bool
    decision: Decision
    side: Side
    position_side: PositionSide | None
    lifecycle: TriggerLifecycle | None
    quantity: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    risk_budget: float | None = None
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
