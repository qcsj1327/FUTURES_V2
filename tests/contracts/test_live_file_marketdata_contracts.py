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
    prices.write_text(
        json.dumps(
            {
                "au": {"price": 100.0, "volume": 10.0, "ts": 1},
                "ag": {"price": 50.0, "volume": 20.0, "ts": 1},
            }
        ),
        encoding="utf-8",
    )

    before = _all_files(tmp_path)

    md = LiveFileMarketData(prices_path=prices)
    assert md.get_last_quote("au").price == 100.0
    assert md.get_last_quotes(["au", "ag"])["ag"].volume == 20.0

    prices.write_text(
        json.dumps({"au": {"price": 101.0, "volume": 11.0, "ts": 2}}),
        encoding="utf-8",
    )
    quote = md.get_last_quote("au")
    assert quote.price == 101.0
    assert quote.ts == 2

    after = _all_files(tmp_path)
    assert before == after


def test_live_file_marketdata_missing_symbol_raises(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps({"au": {"price": 100.0, "volume": 10.0, "ts": 1}}),
        encoding="utf-8",
    )

    md = LiveFileMarketData(prices_path=prices)
    with pytest.raises(KeyError):
        _ = md.get_last_quote("ag")
