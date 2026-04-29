from __future__ import annotations

from app.runtime import Runtime
from app.scheduler import Scheduler
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


def make_decision(signal_id: str) -> SignalDecision:
    return SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="test",
        signal_id=signal_id,
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


def test_scheduler_run_once() -> None:
    runtime = Runtime()
    scheduler = Scheduler(runtime)

    scheduler.run_once(make_decision("s1"))

    assert scheduler.cycles_run == 1
    assert runtime.state.position.quantity > 0


def test_scheduler_run_many() -> None:
    runtime = Runtime()
    scheduler = Scheduler(runtime)

    scheduler.run_many(
        [
            make_decision("s1"),
            make_decision("s2"),
            make_decision("s3"),
        ]
    )

    assert scheduler.cycles_run == 3
    assert runtime.state.position.quantity > 0
