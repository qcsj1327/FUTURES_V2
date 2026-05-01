from __future__ import annotations

from core.signal_router.router import RouterConfig, route
from domain.enums import Decision, Side
from domain.signal import SignalDecision
from strategies.strategy_set import TaggedDecision


def _side_for(decision: Decision) -> Side:
    if decision == Decision.OPEN_LONG:
        return Side.BUY
    if decision == Decision.OPEN_SHORT:
        return Side.SELL
    # HOLD / CLOSE: best-effort
    return getattr(Side, "NONE", Side.BUY)


def _sd(sym: str, decision: Decision) -> SignalDecision:
    return SignalDecision(
        instrument_id=sym,
        trade_instrument_id=sym,
        decision=decision,
        side=_side_for(decision),
        strength=1.0,  # type: ignore[arg-type]
        confidence=1.0,
        reason="test",
    )


def test_router_priority_picks_highest_priority() -> None:
    tagged = [
        TaggedDecision("s_low", _sd("au", Decision.OPEN_LONG)),
        TaggedDecision("s_high", _sd("au", Decision.OPEN_SHORT)),
    ]
    out = route(
        tagged,
        config=RouterConfig(mode="priority"),
        priorities={"s_high": 10, "s_low": 100},
        weights={"s_high": 1.0, "s_low": 1.0},
    )
    assert out[0].strategy_name == "s_high"


def test_router_weighted_vote_picks_highest_weight_decision() -> None:
    tagged = [
        TaggedDecision("a", _sd("au", Decision.OPEN_LONG)),
        TaggedDecision("b", _sd("au", Decision.OPEN_SHORT)),
    ]
    out = route(
        tagged,
        config=RouterConfig(mode="weighted_vote"),
        priorities={"a": 100, "b": 100},
        weights={"a": 0.8, "b": 0.3},
    )
    assert out[0].strategy_name == "a"


def test_router_netting_nets_to_hold_on_tie() -> None:
    tagged = [
        TaggedDecision("a", _sd("au", Decision.OPEN_LONG)),
        TaggedDecision("b", _sd("au", Decision.OPEN_SHORT)),
        TaggedDecision("c", _sd("au", Decision.HOLD)),
    ]
    out = route(
        tagged,
        config=RouterConfig(mode="netting"),
        priorities={"a": 10, "b": 10, "c": 5},
        weights={"a": 1.0, "b": 1.0, "c": 1.0},
    )
    assert out[0].strategy_name == "c"
