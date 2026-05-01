from __future__ import annotations

from core.services.trade.exit_service import ExitService
from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult
from domain.state import PositionKey


def open_long_position(state: StateEngine) -> None:
    order = ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au2506",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=2.0,
        order_type="market",
    )
    result = ExecutionResult(
        success=True,
        status=ExecutionStatus.SUBMITTED,
        order_id="entry_1",
        ts=1,
        fill_price=100.0,
    )
    state.apply(order, result)


def test_exit_service_generates_exit_order_for_long_stop_loss() -> None:
    state = StateEngine(runtime_id="r1")
    exit_service = ExitService()
    open_long_position(state)

    key = PositionKey("au", "au2506", PositionSide.LONG)
    position = state.portfolio.positions[key]

    exit_order = exit_service.create_exit_order(
        position=position,
        current_price=90.0,
        stop_loss=95.0,
    )

    assert exit_order is not None
    assert exit_order.side == Side.SELL
    assert exit_order.position_side == PositionSide.LONG
    assert exit_order.quantity == 2.0
    assert exit_order.order_type == "market"


def test_exit_order_can_be_executed_back_into_state_once() -> None:
    state = StateEngine(runtime_id="r1")
    exit_service = ExitService()
    open_long_position(state)

    key = PositionKey("au", "au2506", PositionSide.LONG)
    position = state.portfolio.positions[key]

    exit_order = exit_service.create_exit_order(
        position=position,
        current_price=90.0,
        stop_loss=95.0,
    )

    assert exit_order is not None

    exit_result = ExecutionResult(
        success=True,
        status=ExecutionStatus.SUBMITTED,
        order_id="exit_1",
        ts=2,
        fill_price=90.0,
    )
    _, closed_position = state.apply(exit_order, exit_result, strategy_name="exit")

    assert closed_position.quantity == 0.0
    assert closed_position.realized_pnl == -20.0

    next_exit = exit_service.create_exit_order(
        position=closed_position,
        current_price=80.0,
        stop_loss=95.0,
    )

    assert next_exit is None


def test_exit_service_does_not_generate_exit_order_when_threshold_not_crossed() -> None:
    state = StateEngine(runtime_id="r1")
    exit_service = ExitService()
    open_long_position(state)

    key = PositionKey("au", "au2506", PositionSide.LONG)
    position = state.portfolio.positions[key]

    exit_order = exit_service.create_exit_order(
        position=position,
        current_price=100.0,
        stop_loss=95.0,
        take_profit=120.0,
    )

    assert exit_order is None


def test_exit_integration_does_not_mutate_position_before_execution() -> None:
    state = StateEngine(runtime_id="r1")
    exit_service = ExitService()
    open_long_position(state)

    key = PositionKey("au", "au2506", PositionSide.LONG)
    position = state.portfolio.positions[key]

    exit_order = exit_service.create_exit_order(
        position=position,
        current_price=90.0,
        stop_loss=95.0,
    )

    assert exit_order is not None
    assert position.quantity == 2.0
    assert state.portfolio.positions[key].quantity == 2.0
