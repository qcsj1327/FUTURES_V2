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
) -> TriggerResult:
    return TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id=instrument_id,
        trade_instrument_id=trade_instrument_id,
        position_side=PositionSide.LONG,
        reason="symbol_weight",
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
        reason="symbol_weight",
    )


def make_portfolio(
    *,
    equity: float | None,
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
        equity=equity,
    )


def test_portfolio_limit_rejects_negative_symbol_weight() -> None:
    with pytest.raises(ValueError, match="max_symbol_weight_must_be_between_0_and_1"):
        PortfolioLimit(max_symbol_weight=-0.1)


def test_portfolio_limit_rejects_symbol_weight_above_one() -> None:
    with pytest.raises(ValueError, match="max_symbol_weight_must_be_between_0_and_1"):
        PortfolioLimit(max_symbol_weight=1.1)


def test_risk_allows_symbol_weight_within_limit() -> None:
    portfolio = make_portfolio(equity=1000.0, quantity=1.0, avg_price=100.0)

    result = RiskEngine(max_symbol_weight=0.3).evaluate(
        make_allocation(quantity=1.0),
        portfolio=portfolio,
        price=100.0,
    )

    assert result.allowed is True
    assert result.quantity == 1.0


def test_risk_rejects_symbol_weight_exceeding_limit() -> None:
    portfolio = make_portfolio(equity=1000.0, quantity=2.0, avg_price=100.0)

    result = RiskEngine(max_symbol_weight=0.25).evaluate(
        make_allocation(quantity=1.0),
        portfolio=portfolio,
        price=100.0,
    )

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "max_symbol_weight_exceeded"


def test_risk_requires_equity_when_symbol_weight_limit_is_enabled() -> None:
    portfolio = make_portfolio(equity=None, quantity=1.0, avg_price=100.0)

    result = RiskEngine(max_symbol_weight=0.5).evaluate(
        make_allocation(quantity=1.0),
        portfolio=portfolio,
        price=100.0,
    )

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "portfolio_equity_required"


def test_symbol_weight_uses_only_same_symbol_exposure() -> None:
    portfolio = make_portfolio(
        equity=1000.0,
        instrument_id="ag",
        trade_instrument_id="ag2506",
        quantity=5.0,
        avg_price=100.0,
    )

    result = RiskEngine(max_symbol_weight=0.2).evaluate(
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


def test_symbol_weight_rule_is_backward_compatible_without_price() -> None:
    portfolio = make_portfolio(equity=1000.0, quantity=10.0, avg_price=100.0)

    result = RiskEngine(max_symbol_weight=0.1).evaluate(
        make_allocation(quantity=1.0),
        portfolio=portfolio,
    )

    assert result.allowed is True
    assert result.quantity == 1.0
