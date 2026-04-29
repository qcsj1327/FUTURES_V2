from __future__ import annotations

from app.runtime import Runtime
from app.scheduler import Scheduler
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


def test_scheduler_run_once() -> None:
    runtime = Runtime()
    scheduler = Scheduler(runtime)

    decision = SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="test",
        signal_id="s1",
        strategy_name="test",
        symbol="au",
        instrument_id="au",
        trade_instrument_id="au_main",
        runtime_id="r1",
        ts=1,
        bar_ts=1,
        bar_time="t",
        position_side=PositionSide.LONG,
    )

    scheduler.run_once(decision)

    assert runtime.state.position.quantity > 0
