from __future__ import annotations

import pytest

from core.services.trade.exit_rules import ExitRules, ExitSignal
from domain.enums import PositionSide
from domain.state import PositionState


def make_position(
    *,
    position_side: PositionSide,
    quantity: float = 1.0,
    avg_price: float | None = 100.0,
) -> PositionState:
    return PositionState(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=position_side,
        quantity=quantity,
        avg_price=avg_price,
    )


def test_long_stop_loss_triggers_when_price_below_stop() -> None:
    signal = ExitRules().evaluate(
        position=make_position(position_side=PositionSide.LONG),
        current_price=90.0,
        stop_loss=95.0,
    )

    assert signal == ExitSignal(triggered=True, reason="stop_loss")


def test_long_take_profit_triggers_when_price_above_target() -> None:
    signal = ExitRules().evaluate(
        position=make_position(position_side=PositionSide.LONG),
        current_price=120.0,
        take_profit=110.0,
    )

    assert signal == ExitSignal(triggered=True, reason="take_profit")


def test_short_stop_loss_triggers_when_price_above_stop() -> None:
    signal = ExitRules().evaluate(
        position=make_position(position_side=PositionSide.SHORT),
        current_price=110.0,
        stop_loss=105.0,
    )

    assert signal == ExitSignal(triggered=True, reason="stop_loss")


def test_short_take_profit_triggers_when_price_below_target() -> None:
    signal = ExitRules().evaluate(
        position=make_position(position_side=PositionSide.SHORT),
        current_price=80.0,
        take_profit=90.0,
    )

    assert signal == ExitSignal(triggered=True, reason="take_profit")


def test_no_exit_when_thresholds_not_crossed() -> None:
    signal = ExitRules().evaluate(
        position=make_position(position_side=PositionSide.LONG),
        current_price=100.0,
        stop_loss=90.0,
        take_profit=110.0,
    )

    assert signal == ExitSignal(triggered=False)


def test_zero_quantity_position_does_not_trigger_exit() -> None:
    signal = ExitRules().evaluate(
        position=make_position(position_side=PositionSide.LONG, quantity=0.0),
        current_price=80.0,
        stop_loss=90.0,
    )

    assert signal == ExitSignal(triggered=False)


def test_exit_rules_require_avg_price_for_active_position() -> None:
    with pytest.raises(ValueError, match="position_avg_price_required"):
        ExitRules().evaluate(
            position=make_position(position_side=PositionSide.LONG, avg_price=None),
            current_price=80.0,
            stop_loss=90.0,
        )


def test_flat_position_never_triggers_exit() -> None:
    signal = ExitRules().evaluate(
        position=make_position(position_side=PositionSide.FLAT),
        current_price=80.0,
        stop_loss=90.0,
        take_profit=110.0,
    )

    assert signal == ExitSignal(triggered=False)
