from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from adapters.marketdata.tqkq_market_data import TqKqMarketData


@dataclass
class _Quote:
    last_price: float | None = None
    volume: float | None = None
    datetime: str | None = None


class _Api:
    def __init__(self) -> None:
        self.q = _Quote(last_price=None, volume=None, datetime=None)
        self._calls = 0
        self._populate_after: int | None = 2

    def get_quote(self, _sym: str) -> Any:
        return self.q

    def wait_update(self, deadline: float | None = None) -> bool:
        _ = deadline
        self._calls += 1
        if self._populate_after is not None and self._calls >= self._populate_after:
            self.q.last_price = 101.0
            self.q.volume = 10.0
            self.q.datetime = "2024-06-17 15:00:00.000000"
        return True

    def close(self) -> None:
        return


def test_tqkq_warmup_waits_until_quotes_ready() -> None:
    api = _Api()
    md = TqKqMarketData(
        tq_symbols={"au": "SHFE.au2406"},
        auth_user="u",
        auth_pass="p",
        api_factory=lambda: api,
        start_background=False,
    )

    md.warmup(["au"], timeout_s=1.0)
    quotes = md.get_last_quotes(["au"])
    q = quotes["au"]
    assert q.price == 101.0
    assert q.volume is not None
    assert q.ts is not None


def test_tqkq_warmup_times_out_with_diagnostics() -> None:
    api = _Api()
    api._populate_after = None
    md = TqKqMarketData(
        tq_symbols={"au": "SHFE.au2406"},
        auth_user="u",
        auth_pass="p",
        api_factory=lambda: api,
        start_background=False,
    )
    with pytest.raises(TimeoutError) as e:
        md.warmup(["au"], timeout_s=0.0)
    msg = str(e.value)
    assert "missing" in msg and "tq_symbols" in msg
