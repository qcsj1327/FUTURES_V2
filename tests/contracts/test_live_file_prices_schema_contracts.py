from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.marketdata.live_market_data import LiveFileMarketData


def test_live_file_quotes_support_main_alias_but_require_equal_values(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    quote = {"price": 100.0, "volume": 10.0, "ts": 1}
    prices.write_text(
        json.dumps({"au": quote, "au_main": quote, "ag": quote, "ag_main": quote}),
        encoding="utf-8",
    )

    md = LiveFileMarketData(prices_path=prices)
    assert md.get_last_quote("au").price == 100.0
    assert md.get_last_quote("au_main").price == 100.0
    assert md.get_last_quote("ag").volume == 10.0
    assert md.get_last_quote("ag_main").ts == 1


def test_live_file_quotes_reject_mismatched_main_alias(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps(
            {
                "au": {"price": 100.0, "volume": 10.0, "ts": 1},
                "au_main": {"price": 101.0, "volume": 10.0, "ts": 1},
            }
        ),
        encoding="utf-8",
    )

    md = LiveFileMarketData(prices_path=prices)
    with pytest.raises(ValueError):
        _ = md.get_last_quote("au_main")


def test_live_file_quotes_require_price_and_ts_with_volume_field(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps({"au": {"price": 180.0, "volume": None, "ts": 1}}),
        encoding="utf-8",
    )

    md = LiveFileMarketData(prices_path=prices)
    quote = md.get_last_quote("au_main")
    assert quote.price == 180.0
    assert quote.volume is None
    assert quote.ts == 1
