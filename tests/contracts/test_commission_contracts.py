from __future__ import annotations

import pytest

from core.state.capital_model import CapitalModel
from core.state.state_engine import StateEngine
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult


def make_order(side: Side, position_side: PositionSide = PositionSide.LONG) -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au2506",
        side=side,
        position_side=position_side,
        quantity=2.0,
        order_type="market",
    )


def make_result(order_id: str, price: float, ts: int = 1) -> ExecutionResult:
    return ExecutionResult(
        success=True,
        status=ExecutionStatus.SUBMITTED,
        order_id=order_id,
        ts=ts,
        fill_price=price,
    )


def test_capital_model_rejects_negative_commission_rate() -> None:
    with pytest.raises(ValueError, match="commission_rate_must_be_non_negative"):
        CapitalModel(commission_rate=-0.01)


def test_buy_commission_reduces_cash() -> None:
    state = StateEngine(runtime_id="r1", commission_rate=0.01)
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    state.apply(make_order(Side.BUY), make_result("o1", 100.0))

    # notional = 200, fee = 2
    assert state.portfolio.cash == 798.0


def test_sell_commission_reduces_cash_proceeds() -> None:
    state = StateEngine(runtime_id="r1", commission_rate=0.01)
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    state.apply(make_order(Side.BUY), make_result("o1", 100.0))
    state.apply(make_order(Side.SELL), make_result("o2", 120.0, ts=2))

    # 1000 - 200 - 2 + 240 - 2.4 = 1035.6
    assert state.portfolio.cash == 1035.6


def test_short_open_commission_reduces_cash_proceeds() -> None:
    state = StateEngine(runtime_id="r1", commission_rate=0.01)
    state.portfolio = state.portfolio.__class__(
        runtime_id="r1",
        positions={},
        cash=1000.0,
    )

    state.apply(
        make_order(Side.SELL, position_side=PositionSide.SHORT),
        make_result("o1", 100.0),
    )

    # short sell proceeds 200 minus fee 2
    assert state.portfolio.cash == 1198.0
