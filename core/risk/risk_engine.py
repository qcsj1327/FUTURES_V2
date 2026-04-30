from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioAllocation
from domain.enums import Decision, PositionSide, Side, TriggerLifecycle
from domain.risk import RiskDecision


class RiskEngine:
    def evaluate(self, allocation: PortfolioAllocation) -> RiskDecision:
        trigger = allocation.trigger

        if not trigger.triggered:
            return self._reject(
                allocation=allocation,
                reason=trigger.reason,
            )

        if trigger.decision == Decision.HOLD:
            return self._reject(
                allocation=allocation,
                reason="triggered_hold",
            )

        if trigger.instrument_id is None:
            return self._reject(
                allocation=allocation,
                reason="missing_instrument_id",
            )

        if trigger.trade_instrument_id is None:
            return self._reject(
                allocation=allocation,
                reason="missing_trade_instrument_id",
            )

        if trigger.side == Side.NONE:
            return self._reject(
                allocation=allocation,
                reason="missing_trade_side",
            )

        if trigger.position_side is None:
            return self._reject(
                allocation=allocation,
                reason="missing_position_side",
            )

        if allocation.quantity is None:
            return self._reject(
                allocation=allocation,
                reason=allocation.reason or "missing_quantity",
            )

        if allocation.quantity <= 0:
            return self._reject(
                allocation=allocation,
                reason="invalid_quantity",
            )

        if trigger.decision == Decision.OPEN_LONG:
            if trigger.side != Side.BUY:
                return self._reject(
                    allocation=allocation,
                    reason="open_long_requires_buy",
                )
            if trigger.position_side != PositionSide.LONG:
                return self._reject(
                    allocation=allocation,
                    reason="open_long_requires_long_position",
                )

        if trigger.decision == Decision.OPEN_SHORT:
            if trigger.side != Side.SELL:
                return self._reject(
                    allocation=allocation,
                    reason="open_short_requires_sell",
                )
            if trigger.position_side != PositionSide.SHORT:
                return self._reject(
                    allocation=allocation,
                    reason="open_short_requires_short_position",
                )

        return RiskDecision(
            instrument_id=trigger.instrument_id,
            trade_instrument_id=trigger.trade_instrument_id,
            allowed=True,
            decision=trigger.decision,
            side=trigger.side,
            position_side=trigger.position_side,
            lifecycle=trigger.lifecycle,
            quantity=allocation.quantity,
            reason=allocation.reason or trigger.reason,
            details={"source": "risk_engine"},
        )

    def _reject(
        self,
        allocation: PortfolioAllocation,
        reason: str | None,
    ) -> RiskDecision:
        trigger = allocation.trigger

        return RiskDecision(
            instrument_id=self._required_or_empty(trigger.instrument_id),
            trade_instrument_id=self._required_or_empty(trigger.trade_instrument_id),
            allowed=False,
            decision=trigger.decision,
            side=trigger.side,
            position_side=trigger.position_side or PositionSide.FLAT,
            lifecycle=trigger.lifecycle
            if trigger.lifecycle != TriggerLifecycle.TRIGGERED
            else TriggerLifecycle.BLOCKED,
            quantity=None,
            reason=reason or "risk_rejected",
            details={"source": "risk_engine"},
        )

    def _required_or_empty(self, value: str | None) -> str:
        if value is None:
            return ""
        return value
