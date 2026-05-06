from __future__ import annotations

from core.execution.event_translator import translate_execution_result
from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.event import OrderEvent
from domain.execution import ExecutionOrder, ExecutionResult
from domain.state import PositionState


def make_order() -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au2506",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=1.0,
        order_type="market",
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


def test_state_does_not_update_on_rejected_execution() -> None:
    state = StateEngine()

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


def test_state_submitted_without_fill_price_updates_order_only() -> None:
    state = StateEngine()

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


def test_state_updates_position_only_on_valid_fill_event() -> None:
    state = StateEngine()

    order = make_order()
    result = ExecutionResult(
        success=True,
        status=ExecutionStatus.FILLED,
        order_id="order_1",
        ts=1,
        fill_price=100.0,
        filled_quantity=1.0,
        remaining_quantity=0.0,
        avg_fill_price=100.0,
    )

    event, position = apply_result(state, order, result)

    assert event is not None
    assert position.quantity == 1.0
    assert position.avg_price == 100.0
    assert len(state.portfolio.positions) == 1
