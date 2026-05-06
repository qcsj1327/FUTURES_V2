from __future__ import annotations

import random

from scripts.local_quote_writer import (
    TIMEFRAME_BUCKETS,
    BarState,
    build_quote_payload,
    build_seed_quote_payload,
    update_bar_state,
    update_price_volume,
)


def test_local_quote_writer_builds_quote_and_all_timeframe_bars() -> None:
    prices = {"au": 100.0}
    volumes = {"au": 10.0}
    bars: BarState = {}

    bars = update_bar_state(bars, prices, volumes, ts=1, tick=1)
    payload = build_quote_payload(prices, volumes, ts=1, bars=bars)

    quote = payload["au"]
    assert quote["price"] == 100.0
    assert quote["volume"] == 10.0
    assert quote["ts"] == 1
    assert quote["turnover"] == 1000.0
    assert quote["return_pct"] == 0.0
    assert quote["bid_price"] < quote["price"] < quote["ask_price"]
    assert set(quote["bars"]) == set(TIMEFRAME_BUCKETS)
    assert quote["bars"]["5m"] == {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "volume": 10.0,
        "ts": 1,
        "vwap": 100.0,
        "range": 0.0,
        "return_pct": 0.0,
    }


def test_local_quote_writer_virtual_bar_buckets_roll_by_tick() -> None:
    bars: BarState = {}
    bars = update_bar_state(
        bars,
        {"au": 100.0},
        {"au": 10.0},
        ts=1,
        tick=1,
        timeframe_buckets={"5m": 2},
    )
    bars = update_bar_state(
        bars,
        {"au": 101.0},
        {"au": 11.0},
        ts=2,
        tick=2,
        timeframe_buckets={"5m": 2},
    )
    assert bars["au"]["5m"].payload() == {
        "open": 100.0,
        "high": 101.0,
        "low": 100.0,
        "close": 101.0,
        "volume": 21.0,
        "ts": 2,
    }

    bars = update_bar_state(
        bars,
        {"au": 99.0},
        {"au": 12.0},
        ts=3,
        tick=3,
        timeframe_buckets={"5m": 2},
    )
    assert bars["au"]["5m"].payload()["open"] == 99.0
    assert bars["au"]["5m"].payload()["volume"] == 12.0


def test_update_price_volume_is_deterministic_with_seed() -> None:
    out1 = update_price_volume(
        {"au": 100.0},
        {"au": 10.0},
        rng=random.Random(7),
        drift=0.001,
        vol=0.002,
        volume_vol=0.003,
    )
    out2 = update_price_volume(
        {"au": 100.0},
        {"au": 10.0},
        rng=random.Random(7),
        drift=0.001,
        vol=0.002,
        volume_vol=0.003,
    )
    assert out1 == out2


def test_seed_quote_payload_covers_all_configured_symbols() -> None:
    payload = build_seed_quote_payload(seed=7, ts=1)

    assert set(payload) == {"au", "ag", "cu", "rb", "zn"}
    for symbol, quote in payload.items():
        assert quote["price"] > 0
        assert quote["volume"] >= 0
        assert quote["ts"] == 1
        assert quote["bid_price"] < quote["price"] < quote["ask_price"]
        assert quote["turnover"] > 0
        assert quote["open_interest"] > 0
        assert set(quote["bars"]) == set(TIMEFRAME_BUCKETS), symbol


def test_seed_quote_payload_uses_symbol_specific_market_profiles() -> None:
    payload_1 = build_seed_quote_payload(seed=7, ts=1)
    payload_2 = build_seed_quote_payload(seed=8, ts=2)

    returns = {
        symbol: round(float(payload_2[symbol]["price"] / payload_1[symbol]["price"] - 1.0), 8)
        for symbol in payload_1
    }
    spreads = {
        symbol: round(float(payload_1[symbol]["spread"] / payload_1[symbol]["price"]), 8)
        for symbol in payload_1
    }

    assert len(set(returns.values())) > 1
    assert len(set(spreads.values())) > 1
