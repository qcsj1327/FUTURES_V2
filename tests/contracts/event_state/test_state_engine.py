from __future__ import annotations

from core.execution.event_translator import translate_execution_result
from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult


def test_state_engine_updates_position() -> None:
    engine = StateEngine()

    order = ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=5.0,
        order_type="market",
    )

    result = ExecutionResult(
        success=True,
        status=ExecutionStatus.FILLED,
        order_id="order_1",
        ts=1,
        fill_price=100.0,
        filled_quantity=5.0,
        remaining_quantity=0.0,
        avg_fill_price=100.0,
    )

    events = translate_execution_result(
        order=order,
        result=result,
        strategy_name="default",
        runtime_id="default",
    )
    assert events.order_event is not None
    engine.apply_order_event(events.order_event)
    assert events.fill_event is not None
    _, position = engine.apply_fill_event(events.fill_event)

    assert position.quantity == 5.0
    assert position.position_side == PositionSide.LONG


def test_state_engine_reject_updates_order_only() -> None:
    engine = StateEngine()
    order = ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=5.0,
        order_type="market",
    )
    result = ExecutionResult(
        success=False,
        status=ExecutionStatus.REJECTED,
        order_id="order_1",
        ts=1,
        reason="rejected",
    )

    events = translate_execution_result(
        order=order,
        result=result,
        strategy_name="default",
        runtime_id="default",
    )
    assert events.order_event is not None
    state = engine.apply_order_event(events.order_event)

    assert state.order_id == "order_1"
    assert events.fill_event is None
    assert engine.portfolio.positions == {}
