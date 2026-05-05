from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.marketdata.live_market_data import LiveFileMarketData


def test_live_file_marketdata_keeps_old_quote_schema_compatible(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps({"au": {"price": 100.0, "volume": 10.0, "ts": 1}}),
        encoding="utf-8",
    )

    quote = LiveFileMarketData(prices_path=prices).get_last_quote("au_main")
    assert quote.price == 100.0
    assert quote.volume == 10.0
    assert quote.ts == 1
    assert quote.bars == {}


def test_live_file_marketdata_reads_multi_timeframe_bars(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps(
            {
                "au": {
                    "price": 101.0,
                    "volume": 12.0,
                    "ts": 2,
                    "bars": {
                        "5m": {
                            "open": 100.0,
                            "high": 102.0,
                            "low": 99.0,
                            "close": 101.0,
                            "volume": 60.0,
                            "ts": 2,
                        },
                        "1h": {
                            "open": 98.0,
                            "high": 103.0,
                            "low": 97.0,
                            "close": 101.5,
                            "volume": 720.0,
                            "ts": 2,
                        },
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    quote = LiveFileMarketData(prices_path=prices).get_last_quote("au")
    assert quote.get_bar("5m") is not None
    assert quote.get_bar("5m").close == 101.0  # type: ignore[union-attr]
    assert quote.get_bar("1h") is not None
    assert quote.get_bar("1h").volume == 720.0  # type: ignore[union-attr]


def test_live_file_marketdata_rejects_invalid_bar_schema(tmp_path: Path) -> None:
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps(
            {
                "au": {
                    "price": 101.0,
                    "volume": 12.0,
                    "ts": 2,
                    "bars": {
                        "5m": {
                            "open": 100.0,
                            "high": 102.0,
                            "low": 99.0,
                            "volume": 60.0,
                            "ts": 2,
                        }
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="invalid quote schema"):
        _ = LiveFileMarketData(prices_path=prices).get_last_quote("au")
