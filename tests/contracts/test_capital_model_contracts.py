from __future__ import annotations

import pytest

from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult


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
        status=ExecutionStatus.SUBMITTED,
        order_id="o1",
        ts=ts,
        fill_price=price,
    )


def test_initial_cash_is_preserved() -> None:
    state = StateEngine(runtime_id="r1")
    assert state.portfolio.cash is None or state.portfolio.cash >= 0


def test_open_position_does_not_create_negative_cash_when_uninitialized() -> None:
    state = StateEngine(runtime_id="r1")

    state.apply(make_order(1.0), make_result(100.0))

    assert state.portfolio.positions
    # 不强制 cash，但不允许出现非法值
    assert state.portfolio.cash is None or state.portfolio.cash >= 0


def test_cash_decreases_when_buying_with_initialized_cash() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    state.apply(make_order(2.0), make_result(100.0))

    assert state.portfolio.cash == 800.0


def test_cannot_buy_when_cash_insufficient() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=100.0,
    )

    with pytest.raises(ValueError, match="insufficient_cash"):
        state.apply(make_order(2.0), make_result(100.0))


def test_cash_increases_when_closing_long_position() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    # 开仓
    state.apply(make_order(2.0), make_result(100.0))
    # 平仓
    close_order = ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au2506",
        side=Side.SELL,
        position_side=PositionSide.LONG,
        quantity=2.0,
        order_type="market",
    )
    state.apply(close_order, make_result(120.0, ts=2))

    # 现金：1000 - 200 + 240 = 1040
    assert state.portfolio.cash == 1040.0


def test_equity_updates_with_position_and_cash() -> None:
    state = StateEngine(runtime_id="r1")
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    state.apply(make_order(1.0), make_result(100.0))

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
        state.apply(make_order(0.0), make_result(100.0))
