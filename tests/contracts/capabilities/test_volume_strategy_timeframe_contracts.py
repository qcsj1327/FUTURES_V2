from __future__ import annotations

from collections.abc import Iterable

from core.services.marketdata.types import MarketBar, MarketQuote
from domain.enums import Decision
from strategies.registry import StrategyRegistry
from strategies.volume._common import quote_for_timeframe

BASE_PARAMS: dict[str, dict[str, object]] = {
    "volume_spike_breakout": {
        "window": 3,
        "spike_mult": 1.5,
        "breakout_lookback": 2,
        "direction": "both",
    },
    "volume_ma_reversion": {
        "window": 3,
        "z_entry": 1.0,
        "z_exit": 0.2,
        "low_vol_mult": 0.9,
    },
    "volume_trend_filter": {
        "momentum_window": 2,
        "vol_window": 3,
        "min_vol_mult": 0.8,
        "direction": "both",
    },
    "volume_observer_guard": {
        "vol_window": 1,
        "min_vol_mult": 1.5,
    },
}


def quote_sequence(length: int) -> list[MarketQuote]:
    return [
        MarketQuote(
            symbol="au",
            price=100.0 + float(i),
            volume=100.0 + float(i * 2),
            ts=i,
            bars={
                "1h": MarketBar(
                    open=200.0 + float(i),
                    high=201.0 + float(i),
                    low=199.0 + float(i),
                    close=200.0 + float(i),
                    volume=300.0 + float(i * 3),
                    ts=i,
                )
            },
        )
        for i in range(length)
    ]


def decisions_for(
    name: str,
    params: dict[str, object],
    quotes: Iterable[MarketQuote],
) -> list[tuple[Decision, str]]:
    strategy = StrategyRegistry.create(name=name, params=params)
    return [(d.decision, d.reason) for d in (strategy.generate("au", q) for q in quotes)]


def test_quote_for_timeframe_returns_derived_quote_with_original_bars() -> None:
    quote = quote_sequence(1)[0]
    derived = quote_for_timeframe(quote, "1h")
    assert derived.price == 200.0
    assert derived.volume == 300.0
    assert derived.ts == 0
    assert derived.bars is quote.bars


def test_volume_strategies_default_spot_matches_explicit_spot() -> None:
    quotes = quote_sequence(20)
    for name, params in BASE_PARAMS.items():
        explicit = {**params, "timeframe": "spot"}
        assert decisions_for(name, params, quotes) == decisions_for(name, explicit, quotes)


def test_all_volume_strategies_hold_when_timeframe_bar_missing() -> None:
    quote = MarketQuote(symbol="au", price=100.0, volume=100.0, ts=1)
    for name, params in BASE_PARAMS.items():
        strategy = StrategyRegistry.create(name=name, params={**params, "timeframe": "1h"})
        decision = strategy.generate("au", quote)
        assert decision.decision == Decision.HOLD
        assert decision.reason == "missing_timeframe_bar"


def test_volume_strategy_timeframe_changes_volume_decision_input() -> None:
    spot_quotes = [
        MarketQuote(
            symbol="au",
            price=100.0,
            volume=100.0,
            ts=1,
            bars={
                "1h": MarketBar(
                    open=100.0,
                    high=100.0,
                    low=100.0,
                    close=100.0,
                    volume=100.0,
                    ts=1,
                )
            },
        ),
        MarketQuote(
            symbol="au",
            price=100.0,
            volume=100.0,
            ts=2,
            bars={
                "1h": MarketBar(
                    open=100.0,
                    high=100.0,
                    low=100.0,
                    close=100.0,
                    volume=300.0,
                    ts=2,
                )
            },
        ),
    ]
    params = BASE_PARAMS["volume_observer_guard"]
    spot = decisions_for("volume_observer_guard", params, spot_quotes)
    one_hour = decisions_for(
        "volume_observer_guard",
        {**params, "timeframe": "1h"},
        spot_quotes,
    )
    assert spot[-1] == (Decision.HOLD, "low_volume_blocked")
    assert one_hour[-1] == (Decision.HOLD, "volume_ok")
