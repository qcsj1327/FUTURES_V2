from __future__ import annotations

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
        trade_instrument_id="au_main",
        position_side=PositionSide.LONG,
        reason="ok",
    )

    result = RiskEngine().evaluate(trigger, quantity=2.0)

    assert result.allowed is True
    assert result.quantity == 2.0
    assert result.instrument_id == "au"
    assert result.trade_instrument_id == "au_main"
    assert result.decision == Decision.OPEN_LONG
    assert result.side == Side.BUY
    assert result.position_side == PositionSide.LONG
    assert result.lifecycle == TriggerLifecycle.TRIGGERED
    assert result.reason == "ok"


def test_risk_engine_blocks_untriggered_result() -> None:
    trigger = TriggerResult(
        decision=Decision.HOLD,
        side=Side.NONE,
        lifecycle=TriggerLifecycle.BLOCKED,
        triggered=False,
        runtime_id="r1",
        reason="blocked",
    )

    result = RiskEngine().evaluate(trigger)

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "blocked"
