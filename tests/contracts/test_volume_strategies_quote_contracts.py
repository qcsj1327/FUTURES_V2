from __future__ import annotations

from collections.abc import Iterable

from adapters.marketdata.base import MarketQuote
from core.signal_router.router import RouterConfig, route
from domain.enums import Decision, Side, SignalStrength
from domain.signal import SignalDecision
from strategies.registry import StrategyRegistry
from strategies.strategy_set import TaggedDecision

STRATEGY_PARAMS: dict[str, dict[str, object]] = {
    "volume_spike_breakout": {
        "window": 5,
        "spike_mult": 1.5,
        "breakout_lookback": 3,
        "direction": "both",
    },
    "volume_ma_reversion": {
        "window": 5,
        "z_entry": 1.0,
        "z_exit": 0.2,
        "low_vol_mult": 0.9,
    },
    "volume_trend_filter": {
        "momentum_window": 3,
        "vol_window": 5,
        "min_vol_mult": 0.8,
        "direction": "both",
    },
    "volume_observer_guard": {
        "vol_window": 5,
        "min_vol_mult": 0.8,
    },
}


def quote_sequence(length: int) -> list[MarketQuote]:
    out: list[MarketQuote] = []
    for i in range(length):
        price = 100.0 + ((i % 17) - 8) * 0.25 + i * 0.03
        volume = 1000.0 + ((i * 37) % 19) * 10.0
        if i % 23 == 0:
            volume = 2300.0
        out.append(MarketQuote(symbol="au", price=price, volume=volume, ts=i))
    return out


def decisions_for(name: str, quotes: Iterable[MarketQuote]) -> list[tuple[Decision, str]]:
    strategy = StrategyRegistry.create(name=name, params=STRATEGY_PARAMS[name])
    return [(d.decision, d.reason) for d in (strategy.generate("au", q) for q in quotes)]


def test_volume_strategies_generate_from_quote_without_exceptions() -> None:
    quote = MarketQuote(symbol="au", price=100.0, volume=1000.0, ts=1)

    for name, params in STRATEGY_PARAMS.items():
        strategy = StrategyRegistry.create(name=name, params=params)
        decision = strategy.generate("au", quote)
        assert decision.symbol == "au"
        assert decision.ts == quote.ts


def test_volume_strategies_hold_when_volume_is_null() -> None:
    quote = MarketQuote(symbol="au", price=100.0, volume=None, ts=1)

    for name, params in STRATEGY_PARAMS.items():
        strategy = StrategyRegistry.create(name=name, params=params)
        decision = strategy.generate("au", quote)
        assert decision.decision == Decision.HOLD
        assert decision.reason == "missing_volume"


def test_volume_strategy_rolling_state_is_deterministic() -> None:
    quotes = quote_sequence(100)

    for name in STRATEGY_PARAMS:
        assert decisions_for(name, quotes) == decisions_for(name, quotes)


def test_volume_strategy_params_are_strict() -> None:
    for name in STRATEGY_PARAMS:
        bad_params = dict(STRATEGY_PARAMS[name])
        first_key = next(iter(bad_params))
        bad_params.pop(first_key)
        try:
            StrategyRegistry.create(name=name, params=bad_params)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{name} accepted missing param {first_key}")


def test_volume_observer_guard_does_not_override_higher_priority_strategy() -> None:
    quote = MarketQuote(symbol="au", price=100.0, volume=1.0, ts=1)
    observer = StrategyRegistry.create(
        name="volume_observer_guard",
        params=STRATEGY_PARAMS["volume_observer_guard"],
    ).generate("au", quote)
    active = SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="active_signal",
        strategy_name="active",
        symbol="au",
    )

    selected = route(
        [
            TaggedDecision("active", active),
            TaggedDecision("volume_observer_guard", observer),
        ],
        config=RouterConfig(mode="priority", tie_breaker="priority"),
        priorities={"active": 1, "volume_observer_guard": 100},
        weights={"active": 1.0, "volume_observer_guard": 1.0},
    )

    assert selected[0].strategy_name == "active"
