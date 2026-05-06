from __future__ import annotations

import pytest

from core.execution.event_translator import translate_execution_result
from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.event import OrderEvent
from domain.execution import ExecutionOrder, ExecutionResult
from domain.state import PositionKey, PositionState


def make_order(
    *,
    side: Side,
    position_side: PositionSide,
    quantity: float,
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
    order_id: str,
    ts: int,
    fill_price: float,
) -> ExecutionResult:
    return ExecutionResult(
        success=True,
        status=ExecutionStatus.FILLED,
        order_id=order_id,
        ts=ts,
        fill_price=fill_price,
    )


def key(position_side: PositionSide) -> PositionKey:
    return PositionKey(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=position_side,
    )


def apply_result(
    state: StateEngine,
    order: ExecutionOrder,
    result: ExecutionResult,
) -> tuple[OrderEvent, PositionState]:
    result = ExecutionResult(
        success=result.success,
        status=ExecutionStatus.FILLED,
        order_id=result.order_id,
        ts=result.ts,
        fill_price=result.fill_price,
        reason=result.reason,
        filled_quantity=order.quantity,
        remaining_quantity=0.0,
        avg_fill_price=result.fill_price,
    )
    events = translate_execution_result(
        order=order,
        result=result,
        strategy_name="default",
        runtime_id=state.runtime_id,
    )
    assert events.order_event is not None
    state.apply_order_event(events.order_event)
    assert events.fill_event is not None
    _, position = state.apply_fill_event(events.fill_event)
    return events.order_event, position


def test_open_long_creates_position() -> None:
    state = StateEngine(runtime_id="r1")

    _, position = apply_result(
        state,
        make_order(side=Side.BUY, position_side=PositionSide.LONG, quantity=2.0),
        make_result(order_id="o1", ts=1, fill_price=100.0),
    )

    assert position.quantity == 2.0
    assert position.avg_price == 100.0
    assert position.realized_pnl == 0.0
    assert state.portfolio.positions[key(PositionSide.LONG)] is position


def test_open_long_adds_quantity_and_recalculates_avg_price() -> None:
    state = StateEngine(runtime_id="r1")

    apply_result(
        state,
        make_order(side=Side.BUY, position_side=PositionSide.LONG, quantity=2.0),
        make_result(order_id="o1", ts=1, fill_price=100.0),
    )
    _, position = apply_result(
        state,
        make_order(side=Side.BUY, position_side=PositionSide.LONG, quantity=3.0),
        make_result(order_id="o2", ts=2, fill_price=110.0),
    )

    assert position.quantity == 5.0
    assert position.avg_price == 106.0
    assert position.realized_pnl == 0.0


def test_open_short_creates_position() -> None:
    state = StateEngine(runtime_id="r1")

    _, position = apply_result(
        state,
        make_order(side=Side.SELL, position_side=PositionSide.SHORT, quantity=4.0),
        make_result(order_id="o1", ts=1, fill_price=200.0),
    )

    assert position.quantity == 4.0
    assert position.avg_price == 200.0
    assert position.realized_pnl == 0.0
    assert state.portfolio.positions[key(PositionSide.SHORT)] is position


def test_open_short_adds_quantity_and_recalculates_avg_price() -> None:
    state = StateEngine(runtime_id="r1")

    apply_result(
        state,
        make_order(side=Side.SELL, position_side=PositionSide.SHORT, quantity=2.0),
        make_result(order_id="o1", ts=1, fill_price=200.0),
    )
    _, position = apply_result(
        state,
        make_order(side=Side.SELL, position_side=PositionSide.SHORT, quantity=2.0),
        make_result(order_id="o2", ts=2, fill_price=180.0),
    )

    assert position.quantity == 4.0
    assert position.avg_price == 190.0
    assert position.realized_pnl == 0.0


def test_close_long_reduces_quantity_and_records_realized_pnl() -> None:
    state = StateEngine(runtime_id="r1")

    apply_result(
        state,
        make_order(side=Side.BUY, position_side=PositionSide.LONG, quantity=5.0),
        make_result(order_id="o1", ts=1, fill_price=100.0),
    )
    _, position = apply_result(
        state,
        make_order(side=Side.SELL, position_side=PositionSide.LONG, quantity=2.0),
        make_result(order_id="o2", ts=2, fill_price=120.0),
    )

    assert position.quantity == 3.0
    assert position.avg_price == 100.0
    assert position.realized_pnl == 40.0
    assert state.portfolio.realized_pnl == 40.0


def test_close_short_reduces_quantity_and_records_realized_pnl() -> None:
    state = StateEngine(runtime_id="r1")

    apply_result(
        state,
        make_order(side=Side.SELL, position_side=PositionSide.SHORT, quantity=5.0),
        make_result(order_id="o1", ts=1, fill_price=200.0),
    )
    _, position = apply_result(
        state,
        make_order(side=Side.BUY, position_side=PositionSide.SHORT, quantity=2.0),
        make_result(order_id="o2", ts=2, fill_price=180.0),
    )

    assert position.quantity == 3.0
    assert position.avg_price == 200.0
    assert position.realized_pnl == 40.0
    assert state.portfolio.realized_pnl == 40.0


def test_close_full_position_keeps_zero_quantity_position() -> None:
    state = StateEngine(runtime_id="r1")

    apply_result(
        state,
        make_order(side=Side.BUY, position_side=PositionSide.LONG, quantity=2.0),
        make_result(order_id="o1", ts=1, fill_price=100.0),
    )
    _, position = apply_result(
        state,
        make_order(side=Side.SELL, position_side=PositionSide.LONG, quantity=2.0),
        make_result(order_id="o2", ts=2, fill_price=110.0),
    )

    assert position.quantity == 0.0
    assert position.avg_price == 100.0
    assert position.realized_pnl == 20.0
    assert state.portfolio.realized_pnl == 20.0
    assert key(PositionSide.LONG) in state.portfolio.positions


def test_close_without_existing_position_is_rejected() -> None:
    state = StateEngine(runtime_id="r1")

    with pytest.raises(ValueError, match="cannot_close_missing_position"):
        apply_result(
            state,
            make_order(side=Side.SELL, position_side=PositionSide.LONG, quantity=1.0),
            make_result(order_id="o1", ts=1, fill_price=100.0),
        )


def test_close_quantity_cannot_exceed_position_quantity() -> None:
    state = StateEngine(runtime_id="r1")

    apply_result(
        state,
        make_order(side=Side.BUY, position_side=PositionSide.LONG, quantity=1.0),
        make_result(order_id="o1", ts=1, fill_price=100.0),
    )

    with pytest.raises(ValueError, match="close_quantity_exceeds_position"):
        apply_result(
            state,
            make_order(side=Side.SELL, position_side=PositionSide.LONG, quantity=2.0),
            make_result(order_id="o2", ts=2, fill_price=110.0),
        )


def test_sell_long_without_existing_position_is_rejected() -> None:
    state = StateEngine(runtime_id="r1")

    with pytest.raises(ValueError, match="cannot_close_missing_position"):
        apply_result(
            state,
            make_order(side=Side.SELL, position_side=PositionSide.LONG, quantity=1.0),
            make_result(order_id="o1", ts=1, fill_price=100.0),
        )


def test_buy_short_without_existing_position_is_rejected() -> None:
    state = StateEngine(runtime_id="r1")

    with pytest.raises(ValueError, match="cannot_close_missing_position"):
        apply_result(
            state,
            make_order(side=Side.BUY, position_side=PositionSide.SHORT, quantity=1.0),
            make_result(order_id="o1", ts=1, fill_price=100.0),
        )


def test_invalid_quantity_is_rejected() -> None:
    state = StateEngine(runtime_id="r1")

    with pytest.raises(ValueError, match="invalid_position_quantity"):
        apply_result(
            state,
            make_order(side=Side.BUY, position_side=PositionSide.LONG, quantity=0.0),
            make_result(order_id="o1", ts=1, fill_price=100.0),
        )
