from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioAllocation
from core.risk.risk_engine import RiskEngine
from domain.enums import Decision, PositionSide, Side, TriggerLifecycle
from domain.state import PortfolioState
from domain.trigger import TriggerResult


def make_trigger() -> TriggerResult:
    return TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
        reason="risk",
    )


def make_allocation(quantity: float = 1.0) -> PortfolioAllocation:
    return PortfolioAllocation(
        trigger=make_trigger(),
        quantity=quantity,
        reason="risk",
    )


def test_risk_budget_reduces_quantity_when_exceeding_budget() -> None:
    portfolio = PortfolioState(runtime_id="r1", cash=1000.0)

    result = RiskEngine(risk_budget=100.0).evaluate(
        make_allocation(quantity=10.0),
        portfolio=portfolio,
        price=100.0,
        stop_loss_distance=10.0,
    )

    assert result.allowed is True
    assert result.quantity == 10.0  # 100 / 10


def test_risk_budget_caps_quantity() -> None:
    portfolio = PortfolioState(runtime_id="r1", cash=1000.0)

    result = RiskEngine(risk_budget=50.0).evaluate(
        make_allocation(quantity=10.0),
        portfolio=portfolio,
        price=100.0,
        stop_loss_distance=10.0,
    )

    assert result.quantity == 5.0


def test_risk_budget_does_not_increase_quantity() -> None:
    portfolio = PortfolioState(runtime_id="r1", cash=1000.0)

    result = RiskEngine(risk_budget=1000.0).evaluate(
        make_allocation(quantity=2.0),
        portfolio=portfolio,
        price=100.0,
        stop_loss_distance=10.0,
    )

    assert result.quantity == 2.0


def test_risk_budget_requires_stop_loss_distance() -> None:
    portfolio = PortfolioState(runtime_id="r1", cash=1000.0)

    result = RiskEngine(risk_budget=100.0).evaluate(
        make_allocation(quantity=2.0),
        portfolio=portfolio,
    )

    assert result.allowed is True
    assert result.quantity == 2.0


def test_risk_budget_respects_cash_constraint() -> None:
    portfolio = PortfolioState(runtime_id="r1", cash=100.0)

    result = RiskEngine(risk_budget=100.0).evaluate(
        make_allocation(quantity=10.0),
        portfolio=portfolio,
        price=100.0,
        stop_loss_distance=10.0,
    )

    assert result.quantity is not None and result.quantity <= 1.0
