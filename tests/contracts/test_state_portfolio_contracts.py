from __future__ import annotations

import pytest

from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, PositionSide, Side
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
        status=ExecutionStatus.SUBMITTED,
        order_id="order_1",
        ts=1,
        fill_price=100.0,
        reason="filled",
    )


def test_state_engine_owns_portfolio_state() -> None:
    state = StateEngine(runtime_id="r1")

    assert isinstance(state.portfolio, PortfolioState)
    assert state.portfolio.runtime_id == "r1"
    assert state.portfolio.positions == {}


def test_state_engine_writes_filled_position_into_portfolio() -> None:
    state = StateEngine(runtime_id="r1")
    order = make_order()
    result = make_result()

    event, position = state.apply(order, result, strategy_name="s1")

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

    state.apply(
        make_order(
            instrument_id="au",
            trade_instrument_id="au2506",
            position_side=PositionSide.LONG,
        ),
        make_result(),
    )
    state.apply(
        make_order(
            instrument_id="ag",
            trade_instrument_id="ag2506",
            position_side=PositionSide.SHORT,
        ),
        ExecutionResult(
            success=True,
            status=ExecutionStatus.SUBMITTED,
            order_id="order_2",
            ts=2,
            fill_price=200.0,
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

    event, position = state.apply(order, result)

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
        state.apply(order, result)


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
        state.apply(order, result)


def test_state_engine_requires_fill_price_for_success() -> None:
    state = StateEngine(runtime_id="r1")
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
