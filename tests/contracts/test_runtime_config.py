from __future__ import annotations

from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


def test_runtime_uses_config_quantity() -> None:
    runtime = Runtime(RuntimeConfig(runtime_id="test", default_quantity=7.0))

    decision = SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="config",
        signal_id="s1",
        strategy_name="test",
        symbol="au",
        instrument_id="au",
        trade_instrument_id="au_main",
        runtime_id="test",
        ts=1,
        bar_ts=1,
        bar_time="t",
        position_side=PositionSide.LONG,
    )

    runtime.run(decision)

    assert runtime.state.position.quantity == 7.0
