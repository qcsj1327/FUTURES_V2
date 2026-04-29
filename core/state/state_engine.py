from __future__ import annotations

from domain.enums import OrderStatus
from domain.event import OrderEvent
from domain.execution import ExecutionOrder, ExecutionResult
from domain.state import PositionState


class StateEngine:
    def __init__(self) -> None:
        self.position = PositionState(
            instrument_id="",
            trade_instrument_id="",
        )

    def apply(
        self,
        order: ExecutionOrder | None,
        result: ExecutionResult,
        strategy_name: str = "default",
    ) -> tuple[OrderEvent | None, PositionState]:
        if order is None:
            return None, self.position

        event = OrderEvent(
            strategy_name=strategy_name,
            instrument_id=order.instrument_id,
            trade_instrument_id=order.trade_instrument_id or "",
            order_id="order_1",
            side=order.side,
            position_side=order.position_side,
            quantity=order.quantity,
            status=OrderStatus.SUBMITTED if result.success else OrderStatus.REJECTED,
            ts=0,
        )

        if result.success:
            fill_price = order.price or 0.0
            if result.reason and result.reason.startswith("filled_at="):
                fill_price = float(result.reason.removeprefix("filled_at="))

            self.position = PositionState(
                instrument_id=order.instrument_id,
                trade_instrument_id=order.trade_instrument_id or "",
                position_side=order.position_side,
                quantity=order.quantity,
                avg_price=fill_price,
            )

        return event, self.position
