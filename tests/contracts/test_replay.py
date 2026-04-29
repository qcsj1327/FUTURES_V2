from __future__ import annotations

from app.replay import ReplayRunner
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


def make_decision(signal_id: str) -> SignalDecision:
    return SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="replay",
        signal_id=signal_id,
        strategy_name="replay_strategy",
        symbol="au",
        instrument_id="au",
        trade_instrument_id="au_main",
        runtime_id="replay",
        ts=1,
        bar_ts=1,
        bar_time="t",
        position_side=PositionSide.LONG,
    )


def test_replay_runner_replays_decisions() -> None:
    runner = ReplayRunner()

    report = runner.run(
        [
            make_decision("s1"),
            make_decision("s2"),
        ]
    )

    assert report.cycles_run == 2
    assert report.orders_submitted == 2
    assert report.final_position_qty > 0
