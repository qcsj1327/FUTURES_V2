from __future__ import annotations

import pytest

from core.portfolio.portfolio_engine import PortfolioAllocation
from core.risk.portfolio_limit import PortfolioLimit
from core.risk.risk_engine import RiskEngine
from domain.enums import Decision, PositionSide, Side, TriggerLifecycle
from domain.state import PortfolioState, PositionKey, PositionState
from domain.trigger import TriggerResult


def make_trigger(
    *,
    instrument_id: str = "au",
    trade_instrument_id: str = "au2506",
    position_side: PositionSide = PositionSide.LONG,
) -> TriggerResult:
    return TriggerResult(
        decision=Decision.OPEN_LONG
        if position_side == PositionSide.LONG
        else Decision.OPEN_SHORT,
        side=Side.BUY if position_side == PositionSide.LONG else Side.SELL,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id=instrument_id,
        trade_instrument_id=trade_instrument_id,
        position_side=position_side,
        reason="portfolio_risk",
    )


def make_allocation(
    *,
    instrument_id: str = "au",
    trade_instrument_id: str = "au2506",
    quantity: float = 1.0,
) -> PortfolioAllocation:
    return PortfolioAllocation(
        trigger=make_trigger(
            instrument_id=instrument_id,
            trade_instrument_id=trade_instrument_id,
        ),
        quantity=quantity,
        reason="portfolio_risk",
    )


def make_portfolio_with_position(
    *,
    instrument_id: str = "au",
    trade_instrument_id: str = "au2506",
    quantity: float = 1.0,
    avg_price: float = 100.0,
) -> PortfolioState:
    key = PositionKey(
        instrument_id=instrument_id,
        trade_instrument_id=trade_instrument_id,
        position_side=PositionSide.LONG,
    )
    position = PositionState(
        instrument_id=instrument_id,
        trade_instrument_id=trade_instrument_id,
        position_side=PositionSide.LONG,
        quantity=quantity,
        avg_price=avg_price,
    )

    return PortfolioState(
        runtime_id="r1",
        positions={key: position},
    )


def test_portfolio_limit_rejects_negative_total_exposure() -> None:
    with pytest.raises(ValueError, match="max_total_exposure_must_be_non_negative"):
        PortfolioLimit(max_total_exposure=-1.0)


def test_portfolio_limit_rejects_negative_active_symbols() -> None:
    with pytest.raises(ValueError, match="max_active_symbols_must_be_non_negative"):
        PortfolioLimit(max_active_symbols=-1)


def test_risk_allows_when_total_exposure_is_within_limit() -> None:
    portfolio = make_portfolio_with_position(quantity=1.0, avg_price=100.0)

    result = RiskEngine(max_total_exposure=300.0).evaluate(
        make_allocation(quantity=1.0),
        portfolio=portfolio,
        price=100.0,
    )

    assert result.allowed is True
    assert result.quantity == 1.0


def test_risk_rejects_when_total_exposure_would_exceed_limit() -> None:
    portfolio = make_portfolio_with_position(quantity=2.0, avg_price=100.0)

    result = RiskEngine(max_total_exposure=250.0).evaluate(
        make_allocation(quantity=1.0),
        portfolio=portfolio,
        price=100.0,
    )

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "max_total_exposure_exceeded"


def test_risk_allows_total_exposure_rule_without_price_for_backward_compatibility() -> None:
    portfolio = make_portfolio_with_position(quantity=2.0, avg_price=100.0)

    result = RiskEngine(max_total_exposure=250.0).evaluate(
        make_allocation(quantity=1.0),
        portfolio=portfolio,
    )

    assert result.allowed is True
    assert result.quantity == 1.0


def test_risk_rejects_when_new_symbol_exceeds_active_symbol_limit() -> None:
    portfolio = make_portfolio_with_position(
        instrument_id="au",
        trade_instrument_id="au2506",
        quantity=1.0,
    )

    result = RiskEngine(max_active_symbols=1).evaluate(
        make_allocation(
            instrument_id="ag",
            trade_instrument_id="ag2506",
            quantity=1.0,
        ),
        portfolio=portfolio,
        price=100.0,
    )

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "max_active_symbols_exceeded"


def test_risk_allows_existing_symbol_when_active_symbol_limit_is_reached() -> None:
    portfolio = make_portfolio_with_position(
        instrument_id="au",
        trade_instrument_id="au2506",
        quantity=1.0,
    )

    result = RiskEngine(max_active_symbols=1).evaluate(
        make_allocation(
            instrument_id="au",
            trade_instrument_id="au2506",
            quantity=1.0,
        ),
        portfolio=portfolio,
        price=100.0,
    )

    assert result.allowed is True
    assert result.quantity == 1.0


def test_zero_quantity_position_does_not_count_as_active_symbol() -> None:
    portfolio = make_portfolio_with_position(
        instrument_id="au",
        trade_instrument_id="au2506",
        quantity=0.0,
    )

    result = RiskEngine(max_active_symbols=1).evaluate(
        make_allocation(
            instrument_id="ag",
            trade_instrument_id="ag2506",
            quantity=1.0,
        ),
        portfolio=portfolio,
        price=100.0,
    )

    assert result.allowed is True
    assert result.quantity == 1.0
