from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

import pytest

from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from adapters.marketdata.live_market_data import LiveFileMarketData


def test_marketdata_adapter_exposes_quote_only_interface() -> None:
    assert hasattr(MarketDataAdapter, "get_last_quote")
    assert hasattr(MarketDataAdapter, "get_last_quotes")
    assert not hasattr(MarketDataAdapter, "get_last_price")
    assert not hasattr(MarketDataAdapter, "get_last_prices")


def test_market_quote_schema_contains_price_volume_and_ts() -> None:
    quote = MarketQuote(symbol="au", price=100.0, volume=None, ts=1)

    assert [f.name for f in fields(MarketQuote)] == ["symbol", "price", "volume", "ts"]
    assert quote.price == 100.0
    assert quote.volume is None
    assert quote.ts == 1


@pytest.mark.parametrize(
    "payload",
    [
        {"au": {"volume": 1000.0, "ts": 1}},
        {"au": {"price": 100.0, "volume": 1000.0}},
        {"au": {"price": 100.0, "ts": 1}},
        {"au": 100.0},
    ],
)
def test_live_file_quote_schema_requires_price_volume_field_and_ts(
    tmp_path: Path,
    payload: dict[str, object],
) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps(payload), encoding="utf-8")

    md = LiveFileMarketData(prices_path=prices)
    with pytest.raises((KeyError, ValueError)):
        _ = md.get_last_quote("au")
