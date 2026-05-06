from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from domain.enums import PositionSide
from domain.state import PortfolioState, PositionKey, PositionState


def test_position_key_is_explicit_identity() -> None:
    key = PositionKey(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
    )

    assert key.instrument_id == "au"
    assert key.trade_instrument_id == "au2506"
    assert key.position_side == PositionSide.LONG


def test_position_key_separates_directional_positions() -> None:
    long_key = PositionKey(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
    )
    short_key = PositionKey(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.SHORT,
    )

    assert long_key != short_key


def test_position_state_remains_single_position_snapshot() -> None:
    position = PositionState(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
        quantity=2.0,
        avg_price=100.0,
        updated_ts=1,
    )

    assert position.instrument_id == "au"
    assert position.trade_instrument_id == "au2506"
    assert position.position_side == PositionSide.LONG
    assert position.quantity == 2.0
    assert position.avg_price == 100.0


def test_portfolio_state_holds_multiple_positions() -> None:
    long_key = PositionKey(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
    )
    short_key = PositionKey(
        instrument_id="ag",
        trade_instrument_id="ag2506",
        position_side=PositionSide.SHORT,
    )

    long_position = PositionState(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
        quantity=1.0,
    )
    short_position = PositionState(
        instrument_id="ag",
        trade_instrument_id="ag2506",
        position_side=PositionSide.SHORT,
        quantity=3.0,
    )

    portfolio = PortfolioState(
        runtime_id="r1",
        positions={
            long_key: long_position,
            short_key: short_position,
        },
        updated_ts=10,
    )

    assert portfolio.runtime_id == "r1"
    assert portfolio.positions[long_key] is long_position
    assert portfolio.positions[short_key] is short_position
    assert len(portfolio.positions) == 2


def test_portfolio_state_is_frozen() -> None:
    portfolio = PortfolioState(runtime_id="r1")

    with pytest.raises(FrozenInstanceError):
        portfolio.runtime_id = "r2"  # type: ignore[misc]


def test_position_key_is_frozen() -> None:
    key = PositionKey(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
    )

    with pytest.raises(FrozenInstanceError):
        key.instrument_id = "ag"  # type: ignore[misc]


def test_position_state_is_intentionally_mutable() -> None:
    position = PositionState(
        instrument_id="au",
        trade_instrument_id="au2506",
    )

    position.quantity = 10.0

    assert position.quantity == 10.0


def test_portfolio_state_positions_are_keyed_by_position_key() -> None:
    key = PositionKey(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
    )
    position = PositionState(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
        quantity=1.0,
    )

    portfolio = PortfolioState(
        runtime_id="r1",
        positions={key: position},
    )

    assert list(portfolio.positions.keys()) == [key]
    assert portfolio.positions[key] is position


def test_legacy_state_domain_types_remain_available() -> None:
    from domain.state import OrderState, PnLSnapshot, StateSnapshot, StrategyState, SystemState

    assert OrderState is not None
    assert StrategyState is not None
    assert SystemState is not None
    assert PnLSnapshot is not None
    assert StateSnapshot is not None
