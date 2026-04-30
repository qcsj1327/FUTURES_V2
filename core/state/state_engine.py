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

        if order.trade_instrument_id is None:
            raise ValueError("ExecutionOrder.trade_instrument_id is required")

        if result.ts is None:
            raise ValueError("ExecutionResult.ts is required")

        event = OrderEvent(
            strategy_name=strategy_name,
            instrument_id=order.instrument_id,
            trade_instrument_id=order.trade_instrument_id,
            order_id=result.order_id if result.order_id is not None else "order_1",
            side=order.side,
            position_side=order.position_side,
            quantity=order.quantity,
            status=OrderStatus.SUBMITTED if result.success else OrderStatus.REJECTED,
            ts=result.ts,
            reason=result.reason,
            client_order_id=order.client_order_id,
        )

        if not result.success:
            return event, self.position

        if result.fill_price is None:
            return event, self.position

        self.position = PositionState(
            instrument_id=order.instrument_id,
            trade_instrument_id=order.trade_instrument_id,
            position_side=order.position_side,
            quantity=order.quantity,
            avg_price=result.fill_price,
            updated_ts=result.ts,
            strategy_name=strategy_name,
        )

        return event, self.position
