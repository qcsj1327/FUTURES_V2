from __future__ import annotations

from core.state.application import FillApplication
from domain.enums import ExecutionStatus, PositionSide, Side
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
        application: FillApplication,
        position: PositionState,
    ) -> tuple[float | None, float | None]:
        _ = application, position
        return portfolio.cash, portfolio.equity

    def pre_validate(
        self,
        *,
        portfolio: PortfolioState,
        application: FillApplication,
    ) -> None:
        _ = portfolio, application
        return

    def _filled_quantity(self, application: FillApplication) -> float:
        if application.status in {
            ExecutionStatus.FILLED,
            ExecutionStatus.PARTIALLY_FILLED,
        }:
            if application.filled_quantity is None:
                raise ValueError("ExecutionResult.filled_quantity is required")

            if application.filled_quantity <= 0:
                raise ValueError("invalid_filled_quantity")

            if application.filled_quantity > application.order_quantity:
                raise ValueError("filled_quantity_exceeds_order_quantity")

            return application.filled_quantity

        if application.order_quantity <= 0:
            raise ValueError("invalid_position_quantity")

        return application.order_quantity

    def _fill_price(self, application: FillApplication) -> float:
        fill_price = application.avg_fill_price

        if fill_price is not None:
            return fill_price

        if application.fill_price is None:
            raise ValueError("ExecutionResult.fill_price is required for capital update")

        return application.fill_price

    def _cash_delta(
        self,
        *,
        application: FillApplication,
        fill_price: float,
        quantity: float,
    ) -> float:
        notional = quantity * fill_price
        commission = notional * self.commission_rate

        if application.position_side == PositionSide.LONG:
            if application.side == Side.BUY:
                return -notional - commission
            if application.side == Side.SELL:
                return notional - commission

        if application.position_side == PositionSide.SHORT:
            if application.side == Side.SELL:
                return notional - commission
            if application.side == Side.BUY:
                return -notional - commission

        raise ValueError("invalid_capital_side")

    def _equity(self, *, cash: float, position: PositionState) -> float:
        if position.avg_price is None:
            return cash

        market_value = position.quantity * position.avg_price

        return cash + market_value
