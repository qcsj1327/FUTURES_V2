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


def test_router_weighted_vote_tie_breaker_priority_picks_highest_priority_strategy() -> None:
    # Same winning decision (OPEN_LONG) from two strategies with equal weights.
    # tie_breaker="priority" should pick the lower priority number.
    tagged = [
        TaggedDecision("a", _sd("au", Decision.OPEN_LONG)),
        TaggedDecision("b", _sd("au", Decision.OPEN_LONG)),
    ]
    out = route(
        tagged,
        config=RouterConfig(mode="weighted_vote", tie_breaker="priority"),
        priorities={"a": 10, "b": 1},
        weights={"a": 1.0, "b": 1.0},
    )
    assert out[0].strategy_name == "b"


def test_router_weighted_vote_tie_breaker_lex_picks_lex_smallest_strategy() -> None:
    tagged = [
        TaggedDecision("b", _sd("au", Decision.OPEN_LONG)),
        TaggedDecision("a", _sd("au", Decision.OPEN_LONG)),
    ]
    out = route(
        tagged,
        config=RouterConfig(mode="weighted_vote", tie_breaker="lex"),
        priorities={"a": 1, "b": 10},
        weights={"a": 1.0, "b": 1.0},
    )
    assert out[0].strategy_name == "a"


def test_router_netting_close_dominates_and_uses_priority_among_close() -> None:
    tagged = [
        TaggedDecision("x", _sd("au", Decision.OPEN_LONG)),
        TaggedDecision("close_low", _sd("au", Decision.CLOSE)),
        TaggedDecision("close_high", _sd("au", Decision.CLOSE)),
    ]
    out = route(
        tagged,
        config=RouterConfig(mode="netting"),
        priorities={"close_high": 5, "close_low": 20, "x": 100},
        weights={"close_high": 1.0, "close_low": 1.0, "x": 1.0},
    )
    assert out[0].strategy_name == "close_high"
