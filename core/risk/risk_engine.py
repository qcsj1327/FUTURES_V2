from __future__ import annotations

from domain.risk import RiskDecision
from domain.trigger import TriggerResult


class RiskEngine:
    def evaluate(self, trigger: TriggerResult, quantity: float = 1.0) -> RiskDecision:
        if not trigger.triggered:
            return RiskDecision(
                instrument_id=trigger.instrument_id or "",
                trade_instrument_id=trigger.trade_instrument_id or "",
                allowed=False,
                decision=trigger.decision,
                side=trigger.side,
                position_side=trigger.position_side,
                lifecycle=trigger.lifecycle,
                quantity=None,
                reason=trigger.reason,
                details={"source": "risk_engine"},
            )

        if trigger.instrument_id is None or trigger.instrument_id == "":
            return RiskDecision(
                instrument_id="",
                trade_instrument_id=trigger.trade_instrument_id or "",
                allowed=False,
                decision=trigger.decision,
                side=trigger.side,
                position_side=trigger.position_side,
                lifecycle=trigger.lifecycle,
                quantity=None,
                reason="missing_instrument_id",
                details={"source": "risk_engine"},
            )

        if trigger.trade_instrument_id is None or trigger.trade_instrument_id == "":
            return RiskDecision(
                instrument_id=trigger.instrument_id,
                trade_instrument_id="",
                allowed=False,
                decision=trigger.decision,
                side=trigger.side,
                position_side=trigger.position_side,
                lifecycle=trigger.lifecycle,
                quantity=None,
                reason="missing_trade_instrument_id",
                details={"source": "risk_engine"},
            )

        if quantity <= 0:
            return RiskDecision(
                instrument_id=trigger.instrument_id,
                trade_instrument_id=trigger.trade_instrument_id,
                allowed=False,
                decision=trigger.decision,
                side=trigger.side,
                position_side=trigger.position_side,
                lifecycle=trigger.lifecycle,
                quantity=None,
                reason="invalid_quantity",
                details={"source": "risk_engine"},
            )

        return RiskDecision(
            instrument_id=trigger.instrument_id,
            trade_instrument_id=trigger.trade_instrument_id,
            allowed=True,
            decision=trigger.decision,
            side=trigger.side,
            position_side=trigger.position_side,
            lifecycle=trigger.lifecycle,
            quantity=quantity,
            reason=trigger.reason,
            details={"source": "risk_engine"},
        )
