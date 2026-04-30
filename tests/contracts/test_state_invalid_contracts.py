from __future__ import annotations

from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, OrderStatus, PositionSide, Side
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
        reason="rejected",
    )

    event, position = state.apply(order, result)

    assert event is not None
    assert event.status == OrderStatus.REJECTED

    # ❗关键：不允许更新持仓
    assert position.quantity == 0.0


def test_state_requires_fill_price_when_success() -> None:
    state = StateEngine()

    order = make_order()
    result = ExecutionResult(
        success=True,
        status=ExecutionStatus.SUBMITTED,
        fill_price=None,  # 非法
    )

    event, position = state.apply(order, result)

    # ❗必须拒绝不完整成交
    assert position.quantity == 0.0


def test_state_updates_position_only_on_valid_fill() -> None:
    state = StateEngine()

    order = make_order()
    result = ExecutionResult(
        success=True,
        status=ExecutionStatus.SUBMITTED,
        fill_price=100.0,
    )

    event, position = state.apply(order, result)

    assert position.quantity == 1.0
    assert position.avg_price == 100.0
