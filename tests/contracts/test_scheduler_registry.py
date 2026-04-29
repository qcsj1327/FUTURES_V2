from __future__ import annotations

from app.runtime_config import RuntimeConfig
from app.runtime_registry import RuntimeRegistry
from app.scheduler_registry import RegistryScheduler
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


def make_decision(signal_id: str) -> SignalDecision:
    return SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="multi",
        signal_id=signal_id,
        strategy_name="test",
        symbol="au",
        instrument_id="au",
        trade_instrument_id="au_main",
        runtime_id="r",
        ts=1,
        bar_ts=1,
        bar_time="t",
        position_side=PositionSide.LONG,
    )


def test_registry_scheduler_multi_runtime() -> None:
    registry = RuntimeRegistry()

    registry.build_from_configs(
        [
            RuntimeConfig(runtime_id="r1", default_quantity=1.0),
            RuntimeConfig(runtime_id="r2", default_quantity=2.0),
        ]
    )

    scheduler = RegistryScheduler(registry)

    reports = scheduler.run(
        {
            "r1": [make_decision("s1")],
            "r2": [make_decision("s2")],
        }
    )

    assert "r1" in reports
    assert "r2" in reports

    assert reports["r1"].orders_submitted == 1
    assert reports["r2"].orders_submitted == 1

    assert reports["r1"].final_position_qty == 1.0
    assert reports["r2"].final_position_qty == 2.0
