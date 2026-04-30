from __future__ import annotations

from domain.enums import PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult
from domain.state import PortfolioState, PositionState


class CapitalModel:
    def __init__(self, commission_rate: float = 0.0) -> None:
        if commission_rate < 0:
            raise ValueError("commission_rate_must_be_non_negative")

        self.commission_rate = commission_rate

    def apply(
        self,
        *,
        portfolio: PortfolioState,
        order: ExecutionOrder,
        result: ExecutionResult,
        position: PositionState,
    ) -> tuple[float | None, float | None]:
        if portfolio.cash is None:
            return None, portfolio.equity

        if result.fill_price is None:
            raise ValueError("ExecutionResult.fill_price is required for capital update")

        cash_delta = self._cash_delta(order=order, fill_price=result.fill_price)
        new_cash = portfolio.cash + cash_delta

        if new_cash < 0:
            raise ValueError("insufficient_cash")

        equity = self._equity(cash=new_cash, position=position)

        return new_cash, equity

    def pre_validate(
        self,
        *,
        portfolio: PortfolioState,
        order: ExecutionOrder,
        result: ExecutionResult,
    ) -> None:
        if portfolio.cash is None:
            return

        if result.fill_price is None:
            raise ValueError("ExecutionResult.fill_price is required for capital update")

        cash_delta = self._cash_delta(order=order, fill_price=result.fill_price)

        if portfolio.cash + cash_delta < 0:
            raise ValueError("insufficient_cash")

    def _cash_delta(self, *, order: ExecutionOrder, fill_price: float) -> float:
        notional = order.quantity * fill_price
        commission = notional * self.commission_rate

        if order.position_side == PositionSide.LONG:
            if order.side == Side.BUY:
                return -notional - commission
            if order.side == Side.SELL:
                return notional - commission

        if order.position_side == PositionSide.SHORT:
            if order.side == Side.SELL:
                return notional - commission
            if order.side == Side.BUY:
                return -notional - commission

        raise ValueError("invalid_capital_side")

    def _equity(self, *, cash: float, position: PositionState) -> float:
        if position.avg_price is None:
            return cash

        market_value = position.quantity * position.avg_price

        return cash + market_value
