from __future__ import annotations

import random

from scripts.mock_prices_writer import (
    TIMEFRAME_BUCKETS,
    BarState,
    build_quote_payload,
    update_bar_state,
    update_price_volume,
)


def test_mock_prices_writer_builds_quote_and_all_timeframe_bars() -> None:
    prices = {"au": 100.0}
    volumes = {"au": 10.0}
    bars: BarState = {}

    bars = update_bar_state(bars, prices, volumes, ts=1, tick=1)
    payload = build_quote_payload(prices, volumes, ts=1, bars=bars)

    quote = payload["au"]
    assert quote["price"] == 100.0
    assert quote["volume"] == 10.0
    assert quote["ts"] == 1
    assert set(quote["bars"]) == set(TIMEFRAME_BUCKETS)
    assert quote["bars"]["5m"] == {
        "open": 100.0,
        "high": 100.0,
        "low": 100.0,
        "close": 100.0,
        "volume": 10.0,
        "ts": 1,
    }


def test_mock_prices_writer_virtual_bar_buckets_roll_by_tick() -> None:
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
