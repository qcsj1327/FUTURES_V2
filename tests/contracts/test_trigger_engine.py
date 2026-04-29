from __future__ import annotations

from core.trigger.trigger_engine import TriggerEngine
from domain.enums import Decision, PositionSide, Side, SignalStrength, TriggerLifecycle
from domain.signal import SignalDecision


def make_decision() -> SignalDecision:
    return SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=0.9,
        reason="test",
        signal_id="s1",
        strategy_name="breakout",
        symbol="SHFE.au",
        instrument_id="au",
        trade_instrument_id="au_main",
        runtime_id="r1",
        ts=1,
        bar_ts=1,
        bar_time="2020-01-01 00:00:00",
        position_side=PositionSide.LONG,
    )


def test_trigger_engine_passthrough() -> None:
    engine = TriggerEngine()
    decision = make_decision()

    result = engine.process(decision, runtime_id="r1")

    assert result.triggered is True
    assert result.lifecycle == TriggerLifecycle.TRIGGERED

    # 核心字段必须透传
    assert result.decision == decision.decision
    assert result.side == decision.side
    assert result.signal_id == decision.signal_id
    assert result.strategy_name == decision.strategy_name
    assert result.symbol == decision.symbol
    assert result.instrument_id == decision.instrument_id
    assert result.trade_instrument_id == decision.trade_instrument_id
