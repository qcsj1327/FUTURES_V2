from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioEngine
from core.risk.risk_engine import RiskEngine
from domain.enums import Decision, PositionSide, Side, TriggerLifecycle
from domain.trigger import TriggerResult


def test_risk_engine_allows_triggered_result() -> None:
    trigger = TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        position_side=PositionSide.LONG,
        reason="ok",
        details={"stop_loss": 440.0, "take_profit": 470.0},
    )

    result = RiskEngine().evaluate(PortfolioEngine().allocate(trigger, default_quantity=2.0))

    assert result.allowed is True
    assert result.quantity == 2.0
    assert result.instrument_id == "au"
    assert result.trade_instrument_id == "SHFE.au2606"
    assert result.decision == Decision.OPEN_LONG
    assert result.side == Side.BUY
    assert result.position_side == PositionSide.LONG
    assert result.lifecycle == TriggerLifecycle.TRIGGERED
    assert result.reason == "ok"
    assert result.stop_loss == 440.0
    assert result.take_profit == 470.0


def test_risk_engine_blocks_untriggered_result() -> None:
    trigger = TriggerResult(
        decision=Decision.HOLD,
        side=Side.NONE,
        lifecycle=TriggerLifecycle.BLOCKED,
        triggered=False,
        runtime_id="r1",
        reason="blocked",
    )

    result = RiskEngine().evaluate(PortfolioEngine().allocate(trigger, default_quantity=1.0))

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "blocked"
