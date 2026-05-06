from __future__ import annotations

from dataclasses import dataclass

from domain.enums import ExecutionStatus, OrderStatus
from domain.event import FillEvent, OrderEvent
from domain.execution import ExecutionOrder, ExecutionResult


@dataclass(frozen=True)
class TranslatedExecutionEvents:
    order_event: OrderEvent | None
    fill_event: FillEvent | None


def translate_execution_result(
    *,
    order: ExecutionOrder | None,
    result: ExecutionResult,
    strategy_name: str,
    runtime_id: str,
    fill_quantity: float | None = None,
) -> TranslatedExecutionEvents:
    if order is None:
        return TranslatedExecutionEvents(order_event=None, fill_event=None)
    if order.trade_instrument_id is None:
        raise ValueError("ExecutionOrder.trade_instrument_id is required")
    if result.ts is None:
        raise ValueError("ExecutionResult.ts is required")
    if result.order_id is None:
        raise ValueError("ExecutionResult.order_id is required")

    order_event = OrderEvent(
        strategy_name=strategy_name,
        instrument_id=order.instrument_id,
        trade_instrument_id=order.trade_instrument_id,
        order_id=result.order_id,
        side=order.side,
        position_side=order.position_side,
        quantity=order.quantity,
        status=_order_status(result),
        ts=result.ts,
        reason=result.reason,
        client_order_id=order.client_order_id,
        runtime_id=runtime_id,
        metadata={
            "remaining_quantity": result.remaining_quantity,
            "filled_quantity": result.filled_quantity,
            "avg_fill_price": result.avg_fill_price,
            "stop_loss": order.stop_loss,
            "take_profit": order.take_profit,
        },
    )

    fill_event = _fill_event(
        order=order,
        result=result,
        strategy_name=strategy_name,
        runtime_id=runtime_id,
        fill_quantity=fill_quantity,
    )
    return TranslatedExecutionEvents(order_event=order_event, fill_event=fill_event)


def _order_status(result: ExecutionResult) -> OrderStatus:
    if not result.success:
        return OrderStatus.REJECTED
    if result.status == ExecutionStatus.PARTIALLY_FILLED:
        return OrderStatus.PARTIALLY_FILLED
    if result.status == ExecutionStatus.FILLED:
        return OrderStatus.FILLED
    return OrderStatus.SUBMITTED


def _fill_event(
    *,
    order: ExecutionOrder,
    result: ExecutionResult,
    strategy_name: str,
    runtime_id: str,
    fill_quantity: float | None,
) -> FillEvent | None:
    if result.status not in {ExecutionStatus.PARTIALLY_FILLED, ExecutionStatus.FILLED}:
        return None
    if order.quantity <= 0:
        raise ValueError("invalid_position_quantity")
    quantity = fill_quantity
    if quantity is None:
        quantity = result.filled_quantity
    if quantity is None or quantity <= 0:
        raise ValueError("ExecutionResult.filled_quantity is required")
    if quantity > order.quantity:
        raise ValueError("filled_quantity_exceeds_order_quantity")
    if result.status == ExecutionStatus.PARTIALLY_FILLED:
        remaining = result.remaining_quantity
        if remaining is None or remaining <= 0:
            raise ValueError("ExecutionResult.remaining_quantity is required")
    if result.status == ExecutionStatus.FILLED:
        remaining = result.remaining_quantity
        if remaining is not None and remaining != 0:
            raise ValueError("filled_remaining_quantity_must_be_zero")
    fill_price = result.fill_price if result.fill_price is not None else result.avg_fill_price
    if fill_price is None:
        raise ValueError("ExecutionResult fill price is required for FillEvent")
    if order.trade_instrument_id is None or result.order_id is None or result.ts is None:
        raise ValueError("ExecutionOrder/result are incomplete for FillEvent")

    return FillEvent(
        strategy_name=strategy_name,
        instrument_id=order.instrument_id,
        trade_instrument_id=order.trade_instrument_id,
        order_id=result.order_id,
        side=order.side,
        position_side=order.position_side,
        quantity=float(quantity),
        fill_price=float(fill_price),
        ts=result.ts,
        client_order_id=order.client_order_id,
        runtime_id=runtime_id,
        metadata={
            "avg_fill_price": result.avg_fill_price,
            "remaining_quantity": result.remaining_quantity,
            "reason": result.reason,
            "execution_status": result.status.value,
            "stop_loss": order.stop_loss,
            "take_profit": order.take_profit,
        },
    )
