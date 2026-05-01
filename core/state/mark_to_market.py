from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from domain.enums import PositionSide
from domain.state import PortfolioState, PositionState


@dataclass(frozen=True)
class MarkToMarketResult:
    cash: float
    equity: float
    unrealized_pnl: float
    market_value: float


class MarkToMarket:
    def value(
        self,
        *,
        portfolio: PortfolioState,
        prices: Mapping[str, float],
    ) -> MarkToMarketResult:
        cash = 0.0 if portfolio.cash is None else portfolio.cash
        market_value = 0.0
        unrealized_pnl = 0.0

        for position in portfolio.positions.values():
            if position.quantity <= 0:
                continue

            if position.avg_price is None:
                raise ValueError("position_avg_price_required")

            current_price = self._price_for_position(position, prices)

            if position.position_side == PositionSide.LONG:
                market_value += position.quantity * current_price
                unrealized_pnl += (
                    current_price - position.avg_price
                ) * position.quantity
                continue

            if position.position_side == PositionSide.SHORT:
                market_value -= position.quantity * current_price
                unrealized_pnl += (
                    position.avg_price - current_price
                ) * position.quantity
                continue

        return MarkToMarketResult(
            cash=cash,
            equity=cash + market_value,
            unrealized_pnl=unrealized_pnl,
            market_value=market_value,
        )

    def _price_for_position(
        self,
        position: PositionState,
        prices: Mapping[str, float],
    ) -> float:
        trade_price = prices.get(position.trade_instrument_id)
        if trade_price is not None:
            return trade_price

        instrument_price = prices.get(position.instrument_id)
        if instrument_price is not None:
            return instrument_price

        raise ValueError("missing_market_price")
