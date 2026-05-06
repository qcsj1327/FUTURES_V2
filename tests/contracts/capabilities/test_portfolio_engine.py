from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioEngine
from domain.enums import Decision, PositionSide, Side, TriggerLifecycle
from domain.trigger import TriggerResult


def make_trigger(triggered: bool = True) -> TriggerResult:
    return TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED if triggered else TriggerLifecycle.BLOCKED,
        triggered=triggered,
        runtime_id="r1",
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
        reason=None if triggered else "blocked",
    )


def test_portfolio_allocates_default_quantity() -> None:
    allocation = PortfolioEngine().allocate(make_trigger(), default_quantity=2.0)

    assert allocation.quantity == 2.0
    assert allocation.trigger.instrument_id == "au"


def test_portfolio_does_not_allocate_untriggered_signal() -> None:
    allocation = PortfolioEngine().allocate(make_trigger(triggered=False), default_quantity=2.0)

    assert allocation.quantity is None
    assert allocation.reason == "blocked"


def test_portfolio_rejects_invalid_quantity_without_fallback() -> None:
    allocation = PortfolioEngine().allocate(make_trigger(), default_quantity=0.0)

    assert allocation.quantity is None
    assert allocation.reason == "invalid_quantity"
