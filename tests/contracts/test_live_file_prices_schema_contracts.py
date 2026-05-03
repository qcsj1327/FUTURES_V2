from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.marketdata.live_market_data import LiveFileMarketData


def test_live_file_quotes_read_base_and_allow_trade_alias_query(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    quote = {"price": 100.0, "volume": 10.0, "ts": 1}
    prices.write_text(
        json.dumps({"au": quote, "ag": quote}),
        encoding="utf-8",
    )

    md = LiveFileMarketData(prices_path=prices)
    assert md.get_last_quote("au").price == 100.0
    assert md.get_last_quote("au_main").price == 100.0
    assert md.get_last_quote("ag").volume == 10.0
    assert md.get_last_quote("ag_main").ts == 1


def test_live_file_quotes_reject_trade_alias_keys(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps(
            {
                "au": {"price": 100.0, "volume": 10.0, "ts": 1},
                "au_main": {"price": 100.0, "volume": 10.0, "ts": 1},
            }
        ),
        encoding="utf-8",
    )

    md = LiveFileMarketData(prices_path=prices)
    with pytest.raises(ValueError):
        _ = md.get_last_quote("au_main")


def test_live_file_quotes_require_price_volume_and_allow_null_ts(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps({"au": {"price": 180.0, "volume": 10.0, "ts": None}}),
        encoding="utf-8",
    )

    md = LiveFileMarketData(prices_path=prices)
    quote = md.get_last_quote("au_main")
    assert quote.price == 180.0
    assert quote.volume == 10.0
    assert quote.ts == 0
