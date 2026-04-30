from __future__ import annotations

from core.state.exit_rules import ExitRules
from domain.enums import PositionSide, Side
from domain.execution import ExecutionOrder
from domain.state import PositionState


def make_position() -> PositionState:
    return PositionState(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
        quantity=2.0,
        avg_price=100.0,
    )


def test_exit_long_generates_sell_order() -> None:
    position = make_position()

    signal = ExitRules().evaluate(
        position=position,
        current_price=80.0,
        stop_loss=90.0,
    )

    assert signal.triggered is True

    order = ExecutionOrder(
        instrument_id=position.instrument_id,
        trade_instrument_id=position.trade_instrument_id,
        side=Side.SELL,
        position_side=PositionSide.LONG,
        quantity=position.quantity,
        order_type="market",
    )

    assert order.side == Side.SELL
    assert order.position_side == PositionSide.LONG
    assert order.quantity == 2.0


def test_exit_short_generates_buy_order() -> None:
    position = PositionState(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.SHORT,
        quantity=3.0,
        avg_price=100.0,
    )

    signal = ExitRules().evaluate(
        position=position,
        current_price=120.0,
        stop_loss=110.0,
    )

    assert signal.triggered is True

    order = ExecutionOrder(
        instrument_id=position.instrument_id,
        trade_instrument_id=position.trade_instrument_id,
        side=Side.BUY,
        position_side=PositionSide.SHORT,
        quantity=position.quantity,
        order_type="market",
    )

    assert order.side == Side.BUY
    assert order.position_side == PositionSide.SHORT
    assert order.quantity == 3.0


def test_exit_does_not_modify_position_state() -> None:
    position = make_position()

    signal = ExitRules().evaluate(
        position=position,
        current_price=80.0,
        stop_loss=90.0,
    )

    assert position.quantity == 2.0
    assert signal.triggered is True
