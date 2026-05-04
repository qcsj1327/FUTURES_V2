from __future__ import annotations

from core.execution.lifecycle_reasons import RISK_POSITION_LIMIT
from domain.execution import ExecutionOrder
from domain.state import PortfolioState


class SymbolPositionLimit:
    def __init__(self, max_position_qty_by_symbol: dict[str, float] | None = None) -> None:
        self.max_position_qty_by_symbol = dict(max_position_qty_by_symbol or {})

    def reject_reason(
        self,
        *,
        order: ExecutionOrder,
        portfolio: PortfolioState,
    ) -> str | None:
        limit = self.max_position_qty_by_symbol.get(order.instrument_id)
        if limit is None:
            return None

        existing_qty = sum(
            position.quantity
            for key, position in portfolio.positions.items()
            if key.instrument_id == order.instrument_id and position.quantity > 0
        )
        if existing_qty + order.quantity > limit:
            return RISK_POSITION_LIMIT
        return None
