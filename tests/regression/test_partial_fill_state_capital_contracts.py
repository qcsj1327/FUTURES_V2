from __future__ import annotations

import pytest

from core.execution.event_translator import translate_execution_result
from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, OrderStatus, PositionSide, Side
from domain.event import OrderEvent
from domain.execution import ExecutionOrder, ExecutionResult
from domain.state import PositionState


def make_order(
    *,
    side: Side = Side.BUY,
    position_side: PositionSide = PositionSide.LONG,
    quantity: float = 10.0,
) -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au2506",
        side=side,
        position_side=position_side,
        quantity=quantity,
        order_type="market",
    )


def make_result(
    *,
    status: ExecutionStatus,
    order_id: str,
    filled_quantity: float | None,
    remaining_quantity: float | None,
    fill_price: float = 100.0,
    avg_fill_price: float | None = None,
    ts: int = 1,
) -> ExecutionResult:
    return ExecutionResult(
        success=True,
        status=status,
        order_id=order_id,
        ts=ts,
        fill_price=fill_price,
        filled_quantity=filled_quantity,
        remaining_quantity=remaining_quantity,
        avg_fill_price=avg_fill_price,
        reason="fill",
    )


def apply_result(
    state: StateEngine,
    order: ExecutionOrder,
    result: ExecutionResult,
) -> tuple[OrderEvent, PositionState]:
    events = translate_execution_result(
        order=order,
        result=result,
        strategy_name="default",
        runtime_id=state.runtime_id,
    )
    assert events.order_event is not None
    state.apply_order_event(events.order_event)
    if events.fill_event is None:
        return events.order_event, state.position
    _, position = state.apply_fill_event(events.fill_event)
    return events.order_event, position


def test_partial_fill_updates_position_by_filled_quantity_only() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    event, position = apply_result(
        state,
        make_order(quantity=10.0),
        make_result(
            status=ExecutionStatus.PARTIALLY_FILLED,
            order_id="o1",
            filled_quantity=4.0,
            remaining_quantity=6.0,
            fill_price=100.0,
        ),
    )

    assert event is not None
    assert event.quantity == 10.0
    assert event.status == OrderStatus.PARTIALLY_FILLED
    assert position.quantity == 4.0
    assert position.avg_price == 100.0
    assert state.portfolio.cash == 1000.0


def test_full_fill_updates_position_by_filled_quantity() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    event, position = apply_result(
        state,
        make_order(quantity=10.0),
        make_result(
            status=ExecutionStatus.FILLED,
            order_id="o1",
            filled_quantity=10.0,
            remaining_quantity=0.0,
            fill_price=100.0,
        ),
    )

    assert event is not None
    assert event.status == OrderStatus.FILLED
    assert position.quantity == 10.0
    assert state.portfolio.cash == 1000.0


def test_partial_close_uses_filled_quantity_only() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    apply_result(
        state,
        make_order(quantity=10.0),
        make_result(
            status=ExecutionStatus.FILLED,
            order_id="entry",
            filled_quantity=10.0,
            remaining_quantity=0.0,
            fill_price=100.0,
            ts=1,
        ),
    )

    _, position = apply_result(
        state,
        make_order(
            side=Side.SELL,
            position_side=PositionSide.LONG,
            quantity=10.0,
        ),
        make_result(
            status=ExecutionStatus.PARTIALLY_FILLED,
            order_id="exit",
            filled_quantity=4.0,
            remaining_quantity=6.0,
            fill_price=120.0,
            ts=2,
        ),
    )

    assert position.quantity == 6.0
    assert position.realized_pnl == 80.0
    assert state.portfolio.cash == 1000.0


def test_avg_fill_price_is_used_for_position_cost_basis() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    _, position = apply_result(
        state,
        make_order(quantity=10.0),
        make_result(
            status=ExecutionStatus.PARTIALLY_FILLED,
            order_id="o1",
            filled_quantity=2.0,
            remaining_quantity=8.0,
            fill_price=100.0,
            avg_fill_price=105.0,
        ),
    )

    assert position.quantity == 2.0
    assert position.avg_price == 105.0
    assert state.portfolio.cash == 1000.0


def test_partial_fill_requires_filled_quantity() -> None:
    state = StateEngine(runtime_id="r1")

    with pytest.raises(ValueError, match="ExecutionResult.filled_quantity is required"):
        apply_result(
            state,
            make_order(quantity=10.0),
            make_result(
                status=ExecutionStatus.PARTIALLY_FILLED,
                order_id="o1",
                filled_quantity=None,
                remaining_quantity=6.0,
                fill_price=100.0,
            ),
        )


def test_filled_quantity_cannot_exceed_order_quantity() -> None:
    state = StateEngine(runtime_id="r1")

    with pytest.raises(ValueError, match="filled_quantity_exceeds_order_quantity"):
        apply_result(
            state,
            make_order(quantity=10.0),
            make_result(
                status=ExecutionStatus.FILLED,
                order_id="o1",
                filled_quantity=11.0,
                remaining_quantity=0.0,
                fill_price=100.0,
            ),
        )
