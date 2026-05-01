from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.marketdata.live_market_data import LiveFileMarketData


def _all_files(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def test_live_file_marketdata_reads_and_updates_without_writing(
    tmp_path: Path,
) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"au": 100.0, "ag": 50.0}), encoding="utf-8")

    before = _all_files(tmp_path)

    md = LiveFileMarketData(prices_path=prices)
    assert md.get_last_price("au") == 100.0
    assert md.get_last_prices(["au", "ag"]) == {"au": 100.0, "ag": 50.0}

    # update file
    prices.write_text(json.dumps({"au": 101.0, "ag": 49.0}), encoding="utf-8")
    assert md.get_last_price("au") == 101.0

    after = _all_files(tmp_path)
    assert before == after  # read-only guarantee


def test_live_file_marketdata_missing_symbol_raises(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"au": 100.0}), encoding="utf-8")

    md = LiveFileMarketData(prices_path=prices)
    with pytest.raises(KeyError):
        _ = md.get_last_price("ag")
