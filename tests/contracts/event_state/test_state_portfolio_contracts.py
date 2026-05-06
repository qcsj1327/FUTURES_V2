from __future__ import annotations

import pytest

from core.execution.event_translator import translate_execution_result
from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.event import OrderEvent
from domain.execution import ExecutionOrder, ExecutionResult
from domain.state import PortfolioState, PositionKey, PositionState


def make_order(
    instrument_id: str = "au",
    trade_instrument_id: str = "au2506",
    position_side: PositionSide = PositionSide.LONG,
) -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id=instrument_id,
        trade_instrument_id=trade_instrument_id,
        side=Side.BUY,
        position_side=position_side,
        quantity=1.0,
        order_type="market",
    )


def make_result() -> ExecutionResult:
    return ExecutionResult(
        success=True,
        status=ExecutionStatus.FILLED,
        order_id="order_1",
        ts=1,
        fill_price=100.0,
        filled_quantity=1.0,
        remaining_quantity=0.0,
        avg_fill_price=100.0,
        reason="filled",
    )


def apply_result(
    state: StateEngine,
    order: ExecutionOrder,
    result: ExecutionResult,
    *,
    strategy_name: str = "default",
) -> tuple[OrderEvent, PositionState]:
    events = translate_execution_result(
        order=order,
        result=result,
        strategy_name=strategy_name,
        runtime_id=state.runtime_id,
    )
    assert events.order_event is not None
    state.apply_order_event(events.order_event)
    if events.fill_event is None:
        return events.order_event, state.position
    _, position = state.apply_fill_event(events.fill_event)
    return events.order_event, position


def test_state_engine_owns_portfolio_state() -> None:
    state = StateEngine(runtime_id="r1")

    assert isinstance(state.portfolio, PortfolioState)
    assert state.portfolio.runtime_id == "r1"
    assert state.portfolio.positions == {}


def test_state_engine_writes_filled_position_into_portfolio() -> None:
    state = StateEngine(runtime_id="r1")
    order = make_order()
    result = make_result()

    event, position = apply_result(state, order, result, strategy_name="s1")

    key = PositionKey(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
    )

    assert event is not None
    assert isinstance(position, PositionState)
    assert state.portfolio.positions[key] is position
    assert position.quantity == 1.0
    assert position.avg_price == 100.0
    assert position.runtime_id == "r1"
    assert position.strategy_name == "s1"
    assert position.updated_ts == 1


def test_state_engine_separates_positions_by_position_key() -> None:
    state = StateEngine(runtime_id="r1")

    apply_result(
        state,
        make_order(
            instrument_id="au",
            trade_instrument_id="au2506",
            position_side=PositionSide.LONG,
        ),
        make_result(),
    )
    apply_result(
        state,
        ExecutionOrder(
            instrument_id="ag",
            trade_instrument_id="ag2506",
            side=Side.SELL,
            position_side=PositionSide.SHORT,
            quantity=1.0,
            order_type="market",
        ),
        ExecutionResult(
            success=True,
            status=ExecutionStatus.FILLED,
            order_id="order_2",
            ts=2,
            fill_price=200.0,
            filled_quantity=1.0,
            remaining_quantity=0.0,
            avg_fill_price=200.0,
            reason="filled",
        ),
    )

    assert len(state.portfolio.positions) == 2

    long_key = PositionKey("au", "au2506", PositionSide.LONG)
    short_key = PositionKey("ag", "ag2506", PositionSide.SHORT)

    assert state.portfolio.positions[long_key].quantity == 1.0
    assert state.portfolio.positions[short_key].avg_price == 200.0


def test_state_engine_does_not_update_portfolio_on_rejected_execution() -> None:
    state = StateEngine(runtime_id="r1")
    order = make_order()
    result = ExecutionResult(
        success=False,
        status=ExecutionStatus.REJECTED,
        order_id="order_1",
        ts=1,
        reason="rejected",
    )

    event, position = apply_result(state, order, result)

    assert event is not None
    assert position is state.position
    assert state.portfolio.positions == {}


def test_state_engine_requires_order_id() -> None:
    state = StateEngine(runtime_id="r1")
    order = make_order()
    result = ExecutionResult(
        success=True,
        status=ExecutionStatus.SUBMITTED,
        order_id=None,
        ts=1,
        fill_price=100.0,
    )

    with pytest.raises(ValueError, match="ExecutionResult.order_id is required"):
        apply_result(state, order, result)


def test_state_engine_requires_result_ts() -> None:
    state = StateEngine(runtime_id="r1")
    order = make_order()
    result = ExecutionResult(
        success=True,
        status=ExecutionStatus.SUBMITTED,
        order_id="order_1",
        ts=None,
        fill_price=100.0,
    )

    with pytest.raises(ValueError, match="ExecutionResult.ts is required"):
        apply_result(state, order, result)


def test_state_engine_submitted_without_fill_price_does_not_update_portfolio() -> None:
    state = StateEngine(runtime_id="r1")
    order = make_order()
    result = ExecutionResult(
        success=True,
        status=ExecutionStatus.SUBMITTED,
        order_id="order_1",
        ts=1,
        fill_price=None,
    )

    event, position = apply_result(state, order, result)

    assert event is not None
    assert position is state.position
    assert state.portfolio.positions == {}
    assert state.orders["order_1"].status.value == "submitted"
