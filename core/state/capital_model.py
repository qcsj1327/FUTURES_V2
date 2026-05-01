from __future__ import annotations

from domain.enums import ExecutionStatus, PositionSide, Side
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

        fill_price = self._fill_price(result)
        filled_quantity = self._filled_quantity(order=order, result=result)
        cash_delta = self._cash_delta(
            order=order,
            fill_price=fill_price,
            quantity=filled_quantity,
        )
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

        fill_price = self._fill_price(result)
        filled_quantity = self._filled_quantity(order=order, result=result)
        cash_delta = self._cash_delta(
            order=order,
            fill_price=fill_price,
            quantity=filled_quantity,
        )

        if portfolio.cash + cash_delta < 0:
            raise ValueError("insufficient_cash")

    def _filled_quantity(
        self,
        *,
        order: ExecutionOrder,
        result: ExecutionResult,
    ) -> float:
        if result.status in {
            ExecutionStatus.FILLED,
            ExecutionStatus.PARTIALLY_FILLED,
        }:
            if result.filled_quantity is None:
                raise ValueError("ExecutionResult.filled_quantity is required")

            if result.filled_quantity <= 0:
                raise ValueError("invalid_filled_quantity")

            if result.filled_quantity > order.quantity:
                raise ValueError("filled_quantity_exceeds_order_quantity")

            return result.filled_quantity

        if order.quantity <= 0:
            raise ValueError("invalid_position_quantity")

        return order.quantity

    def _fill_price(self, result: ExecutionResult) -> float:
        fill_price = result.avg_fill_price

        if fill_price is not None:
            return fill_price

        if result.fill_price is None:
            raise ValueError("ExecutionResult.fill_price is required for capital update")

        return result.fill_price

    def _cash_delta(
        self,
        *,
        order: ExecutionOrder,
        fill_price: float,
        quantity: float,
    ) -> float:
        notional = quantity * fill_price
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
