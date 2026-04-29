from __future__ import annotations

from domain.risk import RiskDecision
from domain.trigger import TriggerResult


class RiskEngine:
    def evaluate(self, trigger: TriggerResult, quantity: float = 1.0) -> RiskDecision:
        return RiskDecision(
            instrument_id=trigger.instrument_id or "",
            trade_instrument_id=trigger.trade_instrument_id or "",
            allowed=trigger.triggered,
            decision=trigger.decision,
            side=trigger.side,
            position_side=trigger.position_side,
            lifecycle=trigger.lifecycle,
            quantity=quantity if trigger.triggered else None,
            reason=trigger.reason,
        )
