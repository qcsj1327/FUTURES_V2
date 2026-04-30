from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioEngine
from core.risk.risk_engine import RiskEngine
from domain.enums import Decision, PositionSide, Side, TriggerLifecycle
from domain.trigger import TriggerResult


def test_portfolio_quantity_flows_into_risk_decision() -> None:
    trigger = TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
    )

    allocation = PortfolioEngine().allocate(trigger, default_quantity=3.0)
    risk = RiskEngine().evaluate(allocation)

    assert risk.allowed is True
    assert risk.quantity == 3.0


def test_risk_rejects_invalid_portfolio_quantity() -> None:
    trigger = TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
    )

    allocation = PortfolioEngine().allocate(trigger, default_quantity=0.0)
    risk = RiskEngine().evaluate(allocation)

    assert risk.allowed is False
    assert risk.quantity is None
    assert risk.reason == "invalid_quantity"
