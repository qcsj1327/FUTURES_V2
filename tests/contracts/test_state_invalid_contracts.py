from __future__ import annotations

import pytest

from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult


def make_order() -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au2506",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=1.0,
        order_type="market",
    )


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

    event, position = state.apply(order, result)

    assert event is not None
    assert position is state.position
    assert state.portfolio.positions == {}


def test_state_requires_fill_price_when_success() -> None:
    state = StateEngine()

    order = make_order()
    result = ExecutionResult(
        success=True,
        status=ExecutionStatus.SUBMITTED,
        order_id="order_1",
        ts=1,
        fill_price=None,
    )

    with pytest.raises(
        ValueError,
        match="ExecutionResult.fill_price is required for successful execution",
    ):
        state.apply(order, result)


def test_state_updates_position_only_on_valid_fill() -> None:
    state = StateEngine()

    order = make_order()
    result = ExecutionResult(
        success=True,
        status=ExecutionStatus.SUBMITTED,
        order_id="order_1",
        ts=1,
        fill_price=100.0,
    )

    event, position = state.apply(order, result)

    assert event is not None
    assert position.quantity == 1.0
    assert position.avg_price == 100.0
    assert len(state.portfolio.positions) == 1
