from __future__ import annotations

import pytest

from core.state.mark_to_market import MarkToMarket, MarkToMarketResult
from domain.enums import PositionSide
from domain.state import PortfolioState, PositionKey, PositionState


def make_portfolio(
    *,
    position_side: PositionSide,
    quantity: float,
    avg_price: float | None,
    cash: float | None = 1000.0,
) -> PortfolioState:
    key = PositionKey("au", "au2506", position_side)
    position = PositionState(
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=position_side,
        quantity=quantity,
        avg_price=avg_price,
    )

    return PortfolioState(
        runtime_id="r1",
        positions={key: position},
        cash=cash,
    )


def test_mark_to_market_long_position() -> None:
    portfolio = make_portfolio(
        position_side=PositionSide.LONG,
        quantity=2.0,
        avg_price=100.0,
        cash=800.0,
    )

    result = MarkToMarket().value(
        portfolio=portfolio,
        prices={"au2506": 120.0},
    )

    assert result == MarkToMarketResult(
        cash=800.0,
        equity=1040.0,
        unrealized_pnl=40.0,
        market_value=240.0,
    )


def test_mark_to_market_short_position() -> None:
    portfolio = make_portfolio(
        position_side=PositionSide.SHORT,
        quantity=2.0,
        avg_price=100.0,
        cash=1200.0,
    )

    result = MarkToMarket().value(
        portfolio=portfolio,
        prices={"au2506": 80.0},
    )

    assert result == MarkToMarketResult(
        cash=1200.0,
        equity=1040.0,
        unrealized_pnl=40.0,
        market_value=-160.0,
    )


def test_mark_to_market_uses_instrument_price_when_trade_price_missing() -> None:
    portfolio = make_portfolio(
        position_side=PositionSide.LONG,
        quantity=1.0,
        avg_price=100.0,
        cash=900.0,
    )

    result = MarkToMarket().value(
        portfolio=portfolio,
        prices={"au": 110.0},
    )

    assert result.equity == 1010.0
    assert result.unrealized_pnl == 10.0


def test_mark_to_market_requires_price_for_active_position() -> None:
    portfolio = make_portfolio(
        position_side=PositionSide.LONG,
        quantity=1.0,
        avg_price=100.0,
    )

    with pytest.raises(ValueError, match="missing_market_price"):
        MarkToMarket().value(portfolio=portfolio, prices={})


def test_mark_to_market_requires_avg_price_for_active_position() -> None:
    portfolio = make_portfolio(
        position_side=PositionSide.LONG,
        quantity=1.0,
        avg_price=None,
    )

    with pytest.raises(ValueError, match="position_avg_price_required"):
        MarkToMarket().value(portfolio=portfolio, prices={"au2506": 100.0})


def test_mark_to_market_ignores_zero_quantity_position() -> None:
    portfolio = make_portfolio(
        position_side=PositionSide.LONG,
        quantity=0.0,
        avg_price=100.0,
        cash=1000.0,
    )

    result = MarkToMarket().value(portfolio=portfolio, prices={})

    assert result.equity == 1000.0
    assert result.unrealized_pnl == 0.0
    assert result.market_value == 0.0
