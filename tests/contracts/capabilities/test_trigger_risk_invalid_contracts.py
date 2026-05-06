from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioEngine
from core.risk.risk_engine import RiskEngine
from core.trigger.trigger_engine import TriggerEngine
from domain.enums import Decision, PositionSide, Side, SignalStrength, TriggerLifecycle
from domain.signal import SignalDecision
from domain.trigger import TriggerResult


def test_trigger_blocks_missing_instrument_id() -> None:
    decision = SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="test",
        signal_id="s1",
        strategy_name="simple",
        symbol="au",
        instrument_id=None,
        trade_instrument_id="au2506",
        runtime_id="r1",
        ts=1,
        bar_ts=1,
        bar_time="1970-01-01T00:00:01Z",
        position_side=PositionSide.LONG,
    )

    result = TriggerEngine().process(decision, runtime_id="r1")

    assert result.triggered is False
    assert result.lifecycle == TriggerLifecycle.BLOCKED
    assert result.reason == "missing_instrument_id"


def test_trigger_blocks_missing_trade_instrument_id() -> None:
    decision = SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="test",
        signal_id="s1",
        strategy_name="simple",
        symbol="au",
        instrument_id="au",
        trade_instrument_id=None,
        runtime_id="r1",
        ts=1,
        bar_ts=1,
        bar_time="1970-01-01T00:00:01Z",
        position_side=PositionSide.LONG,
    )

    result = TriggerEngine().process(decision, runtime_id="r1")

    assert result.triggered is False
    assert result.lifecycle == TriggerLifecycle.BLOCKED
    assert result.reason == "missing_trade_instrument_id"


def test_trigger_blocks_hold_with_directional_side() -> None:
    decision = SignalDecision(
        decision=Decision.HOLD,
        side=Side.BUY,
        strength=SignalStrength.WEAK,
        confidence=0.0,
        reason="hold",
        signal_id="s1",
        strategy_name="simple",
        symbol="au",
        instrument_id="au",
        trade_instrument_id="au2506",
        runtime_id="r1",
        ts=1,
        bar_ts=1,
        bar_time="1970-01-01T00:00:01Z",
        position_side=PositionSide.FLAT,
    )

    result = TriggerEngine().process(decision, runtime_id="r1")

    assert result.triggered is False
    assert result.lifecycle == TriggerLifecycle.BLOCKED
    assert result.reason == "hold_with_directional_side"


def test_risk_preserves_untriggered_reason() -> None:
    trigger = TriggerResult(
        decision=Decision.HOLD,
        side=Side.NONE,
        lifecycle=TriggerLifecycle.BLOCKED,
        triggered=False,
        runtime_id="r1",
        instrument_id=None,
        trade_instrument_id=None,
        reason="blocked_by_trigger",
    )

    result = RiskEngine().evaluate(PortfolioEngine().allocate(trigger, default_quantity=1.0))

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "blocked_by_trigger"


def test_risk_rejects_triggered_missing_instrument_id() -> None:
    trigger = TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id=None,
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
    )

    result = RiskEngine().evaluate(PortfolioEngine().allocate(trigger, default_quantity=1.0))

    assert result.allowed is False
    assert result.quantity is None
    assert result.instrument_id == ""
    assert result.trade_instrument_id == "au2506"
    assert result.reason == "missing_instrument_id"


def test_risk_rejects_triggered_missing_trade_instrument_id() -> None:
    trigger = TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id="au",
        trade_instrument_id=None,
        position_side=PositionSide.LONG,
    )

    result = RiskEngine().evaluate(PortfolioEngine().allocate(trigger, default_quantity=1.0))

    assert result.allowed is False
    assert result.quantity is None
    assert result.instrument_id == "au"
    assert result.trade_instrument_id == ""
    assert result.reason == "missing_trade_instrument_id"


def test_risk_rejects_invalid_quantity_zero() -> None:
    trigger = TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
    )

    result = RiskEngine().evaluate(PortfolioEngine().allocate(trigger, default_quantity=0.0))

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "invalid_quantity"


def test_risk_rejects_invalid_quantity_negative() -> None:
    trigger = TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
    )

    result = RiskEngine().evaluate(PortfolioEngine().allocate(trigger, default_quantity=-1.0))

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "invalid_quantity"


def test_risk_rejects_triggered_hold() -> None:
    trigger = TriggerResult(
        decision=Decision.HOLD,
        side=Side.NONE,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.FLAT,
    )

    result = RiskEngine().evaluate(PortfolioEngine().allocate(trigger, default_quantity=1.0))

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "triggered_hold"


def test_risk_rejects_triggered_none_side_for_trade() -> None:
    trigger = TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.NONE,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id="au",
        trade_instrument_id="au2506",
        position_side=PositionSide.LONG,
    )

    result = RiskEngine().evaluate(PortfolioEngine().allocate(trigger, default_quantity=1.0))

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "missing_trade_side"
