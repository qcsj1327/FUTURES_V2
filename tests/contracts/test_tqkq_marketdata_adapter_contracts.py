from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from adapters.marketdata.tqkq_market_data import TqKqMarketData


@dataclass
class _FakeQuote:
    last_price: float
    volume: float
    datetime: str


class _FakeApi:
    def __init__(self) -> None:
        self.q = _FakeQuote(last_price=100.0, volume=0.0, datetime="2024-06-17 14:59:59.000000")

    def get_quote(self, _sym: str) -> Any:
        return self.q

    def wait_update(self, deadline: float | None = None) -> bool:
        _ = deadline
        return True

    def close(self) -> None:
        return


def test_tqkq_maps_main_to_base_and_returns_delta_volume() -> None:
    api = _FakeApi()

    md = TqKqMarketData(
        tq_symbols={"au": "SHFE.au2406"},
        auth_user="u",
        auth_pass="p",
        api_factory=lambda: api,
        start_background=False,
    )

    # first poll: volume=0 -> delta=0
    md._poll_once()
    q1 = md.get_last_quote("au_main")
    assert q1.price == 100.0
    assert q1.volume == 0.0

    # update quote: cumulative volume increases
    api.q.last_price = 101.0
    api.q.volume = 10.0
    api.q.datetime = "2024-06-17 15:00:00.000000"
    md._poll_once()
    q2 = md.get_last_quote("au")
    assert q2.price == 101.0
    assert q2.volume == 10.0

    # increase again: delta should be diff
    api.q.volume = 15.0
    md._poll_once()
    q3 = md.get_last_quote("au")
    assert q3.volume == 5.0


def test_tqkq_missing_symbol_raises() -> None:
    api = _FakeApi()
    md = TqKqMarketData(
        tq_symbols={"au": "SHFE.au2406"},
        auth_user="u",
        auth_pass="p",
        api_factory=lambda: api,
        start_background=False,
    )
    md._poll_once()
    with pytest.raises(KeyError):
        _ = md.get_last_quote("ag")
