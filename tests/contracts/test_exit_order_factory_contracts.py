from __future__ import annotations

import pytest

from core.services.trade.exit_order_factory import ExitOrderFactory
from core.services.trade.exit_rules import ExitSignal
from domain.enums import PositionSide, Side
from domain.state import PositionState


def make_position(
    *,
    position_side: PositionSide,
    quantity: float = 2.0,
) -> PositionState:
    return PositionState(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=position_side,
        quantity=quantity,
        avg_price=100.0,
    )


def test_exit_long_generates_sell_order() -> None:
    order = ExitOrderFactory().create(
        position=make_position(position_side=PositionSide.LONG),
        signal=ExitSignal(triggered=True, reason="stop_loss"),
    )

    assert order is not None
    assert order.side == Side.SELL
    assert order.position_side == PositionSide.LONG
    assert order.quantity == 2.0
    assert order.order_type == "market"


def test_exit_short_generates_buy_order() -> None:
    order = ExitOrderFactory().create(
        position=make_position(position_side=PositionSide.SHORT, quantity=3.0),
        signal=ExitSignal(triggered=True, reason="take_profit"),
    )

    assert order is not None
    assert order.side == Side.BUY
    assert order.position_side == PositionSide.SHORT
    assert order.quantity == 3.0
    assert order.order_type == "market"


def test_no_order_when_exit_signal_not_triggered() -> None:
    order = ExitOrderFactory().create(
        position=make_position(position_side=PositionSide.LONG),
        signal=ExitSignal(triggered=False),
    )

    assert order is None


def test_no_order_when_position_quantity_is_zero() -> None:
    order = ExitOrderFactory().create(
        position=make_position(position_side=PositionSide.LONG, quantity=0.0),
        signal=ExitSignal(triggered=True, reason="stop_loss"),
    )

    assert order is None


def test_flat_position_cannot_generate_exit_order() -> None:
    with pytest.raises(ValueError, match="flat_position_cannot_exit"):
        ExitOrderFactory().create(
            position=make_position(position_side=PositionSide.FLAT),
            signal=ExitSignal(triggered=True, reason="stop_loss"),
        )
