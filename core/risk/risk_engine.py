from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioAllocation
from domain.enums import Decision, Side
from domain.risk import RiskDecision
from domain.state import PortfolioState, PositionKey


class RiskEngine:
    def __init__(self, max_position_qty: float | None = None) -> None:
        self.max_position_qty = max_position_qty

    def evaluate(
        self,
        allocation: PortfolioAllocation,
        portfolio: PortfolioState | None = None,
    ) -> RiskDecision:
        trigger = allocation.trigger

        if not trigger.triggered:
            return RiskDecision(
                instrument_id=trigger.instrument_id if trigger.instrument_id is not None else "",
                trade_instrument_id=(
                    trigger.trade_instrument_id
                    if trigger.trade_instrument_id is not None
                    else ""
                ),
                allowed=False,
                decision=trigger.decision,
                side=trigger.side,
                position_side=trigger.position_side,
                lifecycle=trigger.lifecycle,
                quantity=None,
                reason=trigger.reason,
                details={"source": "risk_engine"},
            )

        if trigger.instrument_id is None:
            return self._reject(allocation, "missing_instrument_id")

        if trigger.trade_instrument_id is None:
            return self._reject(allocation, "missing_trade_instrument_id")

        if trigger.decision == Decision.HOLD:
            return self._reject(allocation, "triggered_hold")

        if trigger.side == Side.NONE:
            return self._reject(allocation, "missing_trade_side")

        if allocation.quantity is None or allocation.quantity <= 0:
            return self._reject(allocation, allocation.reason or "invalid_quantity")

        if self._exceeds_position_limit(allocation, portfolio):
            return self._reject(allocation, "max_position_exceeded")

        return RiskDecision(
            instrument_id=trigger.instrument_id,
            trade_instrument_id=trigger.trade_instrument_id,
            allowed=True,
            decision=trigger.decision,
            side=trigger.side,
            position_side=trigger.position_side,
            lifecycle=trigger.lifecycle,
            quantity=allocation.quantity,
            stop_loss=None,
            take_profit=None,
            risk_budget=None,
            reason=allocation.reason or trigger.reason,
            details={"source": "risk_engine"},
        )

    def _exceeds_position_limit(
        self,
        allocation: PortfolioAllocation,
        portfolio: PortfolioState | None,
    ) -> bool:
        if self.max_position_qty is None:
            return False

        if allocation.quantity is None:
            return False

        trigger = allocation.trigger

        if (
            portfolio is None
            or trigger.instrument_id is None
            or trigger.trade_instrument_id is None
            or trigger.position_side is None
        ):
            return allocation.quantity > self.max_position_qty

        key = PositionKey(
            instrument_id=trigger.instrument_id,
            trade_instrument_id=trigger.trade_instrument_id,
            position_side=trigger.position_side,
        )
        existing = portfolio.positions.get(key)
        existing_quantity = 0.0 if existing is None else existing.quantity

        return existing_quantity + allocation.quantity > self.max_position_qty

    def _reject(self, allocation: PortfolioAllocation, reason: str) -> RiskDecision:
        trigger = allocation.trigger

        return RiskDecision(
            instrument_id=trigger.instrument_id if trigger.instrument_id is not None else "",
            trade_instrument_id=(
                trigger.trade_instrument_id
                if trigger.trade_instrument_id is not None
                else ""
            ),
            allowed=False,
            decision=trigger.decision,
            side=trigger.side,
            position_side=trigger.position_side,
            lifecycle=trigger.lifecycle,
            quantity=None,
            stop_loss=None,
            take_profit=None,
            risk_budget=None,
            reason=reason,
            details={"source": "risk_engine"},
        )
