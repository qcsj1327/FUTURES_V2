from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioAllocation
from core.risk.risk_engine import RiskEngine
from domain.enums import Decision, PositionSide, Side, TriggerLifecycle
from domain.state import PortfolioState, PositionKey, PositionState
from domain.trigger import TriggerResult


def make_trigger(quantity_side: PositionSide = PositionSide.LONG) -> TriggerResult:
    return TriggerResult(
        decision=Decision.OPEN_LONG if quantity_side == PositionSide.LONG else Decision.OPEN_SHORT,
        side=Side.BUY if quantity_side == PositionSide.LONG else Side.SELL,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=quantity_side,
        reason="risk",
    )


def make_allocation(quantity: float = 1.0) -> PortfolioAllocation:
    return PortfolioAllocation(
        trigger=make_trigger(),
        quantity=quantity,
        reason="risk",
    )


def test_risk_allows_when_position_below_max_limit() -> None:
    portfolio = PortfolioState(
        runtime_id="r1",
        positions={
            PositionKey("au", "au2506", PositionSide.LONG): PositionState(
                instrument_id="au",
                trade_instrument_id="au2506",
                position_side=PositionSide.LONG,
                quantity=1.0,
            )
        },
    )

    result = RiskEngine(max_position_qty=3.0).evaluate(
        make_allocation(quantity=1.0),
        portfolio=portfolio,
    )

    assert result.allowed is True
    assert result.quantity == 1.0


def test_risk_rejects_when_position_would_exceed_max_limit() -> None:
    portfolio = PortfolioState(
        runtime_id="r1",
        positions={
            PositionKey("au", "au2506", PositionSide.LONG): PositionState(
                instrument_id="au",
                trade_instrument_id="au2506",
                position_side=PositionSide.LONG,
                quantity=2.5,
            )
        },
    )

    result = RiskEngine(max_position_qty=3.0).evaluate(
        make_allocation(quantity=1.0),
        portfolio=portfolio,
    )

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "max_position_exceeded"


def test_risk_allows_when_no_portfolio_is_supplied_for_backward_compatibility() -> None:
    result = RiskEngine(max_position_qty=1.0).evaluate(make_allocation(quantity=1.0))

    assert result.allowed is True
    assert result.quantity == 1.0


def test_risk_rejects_when_single_order_exceeds_max_limit() -> None:
    portfolio = PortfolioState(runtime_id="r1")

    result = RiskEngine(max_position_qty=3.0).evaluate(
        make_allocation(quantity=4.0),
        portfolio=portfolio,
    )

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "max_position_exceeded"


def test_risk_position_limit_is_keyed_by_instrument_and_side() -> None:
    portfolio = PortfolioState(
        runtime_id="r1",
        positions={
            PositionKey("ag", "ag2506", PositionSide.LONG): PositionState(
                instrument_id="ag",
                trade_instrument_id="ag2506",
                position_side=PositionSide.LONG,
                quantity=100.0,
            )
        },
    )

    result = RiskEngine(max_position_qty=3.0).evaluate(
        make_allocation(quantity=1.0),
        portfolio=portfolio,
    )

    assert result.allowed is True
    assert result.quantity == 1.0
