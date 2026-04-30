from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioAllocation
from domain.state import PortfolioState, PositionKey


class PositionLimit:
    def __init__(self, max_position_qty: float | None = None) -> None:
        self.max_position_qty = max_position_qty

    def exceeded(
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
