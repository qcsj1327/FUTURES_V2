from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.marketdata.live_market_data import LiveFileMarketData


def test_live_file_prices_supports_main_alias_but_requires_equal_values(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps({"au": 100.0, "au_main": 100.0, "ag": 50.0, "ag_main": 50.0}),
        encoding="utf-8",
    )

    md = LiveFileMarketData(prices_path=prices)
    assert md.get_last_price("au") == 100.0
    assert md.get_last_price("au_main") == 100.0
    assert md.get_last_price("ag") == 50.0
    assert md.get_last_price("ag_main") == 50.0


def test_live_file_prices_rejects_mismatched_main_alias(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps({"au": 100.0, "au_main": 101.0}),
        encoding="utf-8",
    )

    md = LiveFileMarketData(prices_path=prices)
    with pytest.raises(ValueError):
        _ = md.get_last_price("au_main")


def test_live_file_prices_recommends_base_symbols(tmp_path: Path) -> None:
    # preferred format: only base symbols (no *_main keys)
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"au": 180.0, "ag": 50.0}), encoding="utf-8")

    md = LiveFileMarketData(prices_path=prices)
    # base works
    assert md.get_last_price("au") == 180.0
    # *_main should still work via alias (read-only compatibility)
    assert md.get_last_price("au_main") == 180.0
