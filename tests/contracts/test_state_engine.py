from __future__ import annotations

from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult


def test_state_engine_updates_position() -> None:
    engine = StateEngine()

    order = ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au_main",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=5.0,
        order_type="market",
    )

    result = ExecutionResult(success=True, status=ExecutionStatus.SUBMITTED)

    event, position = engine.apply(order, result)

    assert event is not None
    assert position.quantity == 5.0
    assert position.position_side == PositionSide.LONG


def test_state_engine_reject() -> None:
    engine = StateEngine()

    result = ExecutionResult(success=False, status=ExecutionStatus.REJECTED)

    event, position = engine.apply(None, result)

    assert event is None
