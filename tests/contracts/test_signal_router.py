from __future__ import annotations

from core.signal_router.signal_router import SignalRouter
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


def make(decision: Decision) -> SignalDecision:
    return SignalDecision(
        decision=decision,
        side=Side.BUY if decision != Decision.HOLD else Side.NONE,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="test",
        signal_id="s",
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


def test_router_selects_first_non_hold() -> None:
    router = SignalRouter()

    signals = [
        make(Decision.HOLD),
        make(Decision.OPEN_LONG),
        make(Decision.OPEN_SHORT),
    ]

    result = router.select(signals)

    assert result.decision == Decision.OPEN_LONG


def test_router_all_hold() -> None:
    router = SignalRouter()

    signals = [
        make(Decision.HOLD),
        make(Decision.HOLD),
    ]

    result = router.select(signals)

    assert result.decision == Decision.HOLD
