from __future__ import annotations

from app.runtime import Runtime
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


def test_runtime_full_flow() -> None:
    runtime = Runtime()

    decision = SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=0.9,
        reason="test",
        signal_id="s1",
        strategy_name="breakout",
        symbol="au",
        instrument_id="au",
        trade_instrument_id="au_main",
        runtime_id="r1",
        ts=1,
        bar_ts=1,
        bar_time="t",
        position_side=PositionSide.LONG,
    )

    runtime.run(decision)

    assert runtime.state.position.quantity > 0
