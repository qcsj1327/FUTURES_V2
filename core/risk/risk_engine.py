from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioAllocation
from core.risk.portfolio_limit import PortfolioLimit
from core.risk.position_limit import PositionLimit
from core.risk.risk_budget import RiskBudget
from domain.enums import Decision, Side
from domain.risk import RiskDecision
from domain.state import PortfolioState


class RiskEngine:
    def __init__(
        self,
        max_position_qty: float | None = None,
        risk_budget: float | None = None,
        max_total_exposure: float | None = None,
        max_active_symbols: int | None = None,
        max_symbol_weight: float | None = None,
    ) -> None:
        self.position_limit = PositionLimit(max_position_qty=max_position_qty)
        self.risk_budget = RiskBudget(risk_budget=risk_budget)
        self.portfolio_limit = PortfolioLimit(
            max_total_exposure=max_total_exposure,
            max_active_symbols=max_active_symbols,
            max_symbol_weight=max_symbol_weight,
        )

    def evaluate(
        self,
        allocation: PortfolioAllocation,
        portfolio: PortfolioState | None = None,
        *,
        price: float | None = None,
        stop_loss_distance: float | None = None,
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

        adjusted_quantity = self.risk_budget.adjust_quantity(
            allocation=allocation,
            portfolio=portfolio,
            price=price,
            stop_loss_distance=stop_loss_distance,
        )

        if adjusted_quantity is None or adjusted_quantity <= 0:
            return self._reject(allocation, "invalid_quantity")

        adjusted_allocation = allocation.__class__(
            trigger=allocation.trigger,
            quantity=adjusted_quantity,
            reason=allocation.reason,
            details=allocation.details,
        )

        if self._exceeds_position_limit(adjusted_allocation, portfolio):
            return self._reject(adjusted_allocation, "max_position_exceeded")

        portfolio_limit_reason = self.portfolio_limit.check(
            allocation=adjusted_allocation,
            portfolio=portfolio,
            price=price,
        )
        if portfolio_limit_reason is not None:
            return self._reject(adjusted_allocation, portfolio_limit_reason)

        return RiskDecision(
            instrument_id=trigger.instrument_id,
            trade_instrument_id=trigger.trade_instrument_id,
            allowed=True,
            decision=trigger.decision,
            side=trigger.side,
            position_side=trigger.position_side,
            lifecycle=trigger.lifecycle,
            quantity=adjusted_quantity,
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
        return self.position_limit.exceeded(allocation, portfolio)

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
