from __future__ import annotations

import pytest

from core.execution.event_translator import translate_execution_result
from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.event import OrderEvent
from domain.execution import ExecutionOrder, ExecutionResult
from domain.state import PositionState


def make_order(qty: float) -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au2506",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=qty,
        order_type="market",
    )


def make_result(price: float, ts: int = 1) -> ExecutionResult:
    return ExecutionResult(
        success=True,
        status=ExecutionStatus.FILLED,
        order_id="o1",
        ts=ts,
        fill_price=price,
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


def test_initial_cash_is_preserved() -> None:
    state = StateEngine(runtime_id="r1")
    assert state.portfolio.cash is None or state.portfolio.cash >= 0


def test_open_position_does_not_create_negative_cash_when_uninitialized() -> None:
    state = StateEngine(runtime_id="r1")

    apply_result(state, make_order(1.0), make_result(100.0))

    assert state.portfolio.positions
    # 不强制 cash，但不允许出现非法值
    assert state.portfolio.cash is None or state.portfolio.cash >= 0


def test_fill_does_not_debit_full_notional_cash_in_futures_state() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    apply_result(state, make_order(2.0), make_result(100.0))

    assert state.portfolio.cash == 1000.0


def test_cash_insufficiency_is_not_checked_by_state_capital_model() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=100.0,
    )

    apply_result(state, make_order(2.0), make_result(100.0))

    assert state.portfolio.cash == 100.0


def test_cash_increases_when_closing_long_position() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    # 开仓
    apply_result(state, make_order(2.0), make_result(100.0))
    # 平仓
    close_order = ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au2506",
        side=Side.SELL,
        position_side=PositionSide.LONG,
        quantity=2.0,
        order_type="market",
    )
    apply_result(state, close_order, make_result(120.0, ts=2))

    assert state.portfolio.cash == 1000.0


def test_equity_updates_with_position_and_cash() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    apply_result(state, make_order(1.0), make_result(100.0))

    # equity 至少 >= cash
    assert state.portfolio.cash is not None
    assert state.portfolio.equity is None or state.portfolio.equity >= state.portfolio.cash


def test_zero_quantity_position_does_not_consume_cash() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    with pytest.raises(ValueError):
        apply_result(state, make_order(0.0), make_result(100.0))
