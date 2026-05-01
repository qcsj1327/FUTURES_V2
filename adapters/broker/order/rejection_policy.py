from __future__ import annotations

from collections.abc import Iterable

from domain.execution import ExecutionOrder


class RejectionPolicy:
    def __init__(
        self,
        *,
        reject_next_order: bool = False,
        rejected_symbols: Iterable[str] | None = None,
        reject_above_quantity: float | None = None,
    ) -> None:
        if reject_above_quantity is not None and reject_above_quantity < 0:
            raise ValueError("reject_above_quantity_must_be_non_negative")

        self.reject_next_order = reject_next_order
        self.rejected_symbols = (
            set() if rejected_symbols is None else set(rejected_symbols)
        )
        self.reject_above_quantity = reject_above_quantity

    def reject_reason(self, order: ExecutionOrder) -> str | None:
        if self.reject_next_order:
            self.reject_next_order = False
            return "reject_next_order"

        if self._matches_symbol(order):
            return "rejected_symbol"

        if (
            self.reject_above_quantity is not None
            and order.quantity > self.reject_above_quantity
        ):
            return "quantity_rejected"

        return None

    def _matches_symbol(self, order: ExecutionOrder) -> bool:
        symbols = {order.instrument_id}

        if order.trade_instrument_id is not None:
            symbols.add(order.trade_instrument_id)

        return bool(symbols & self.rejected_symbols)
