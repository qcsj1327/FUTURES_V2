from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adapters.broker.tqkq_live_broker import TqKqLiveBroker
from adapters.marketdata.tqkq_market_data import TqKqMarketData


@dataclass
class _Quote:
    last_price: float = 450.0
    volume: float = 1000.0
    datetime: str = "2026-05-04 10:00:00.000000"


class _FakeApi:
    def __init__(self, *, fail_wait: bool = False) -> None:
        self.quote = _Quote()
        self.close_calls = 0
        self.fail_wait = fail_wait

    def get_quote(self, _symbol: str) -> Any:
        return self.quote

    def wait_update(self, deadline: float | None = None) -> bool:
        _ = deadline
        if self.fail_wait:
            raise RuntimeError("fake wait failure")
        return True

    def close(self) -> None:
        self.close_calls += 1


def test_shutdown_idempotent_marketdata_and_broker_close_contract() -> None:
    api = _FakeApi()
    md = TqKqMarketData(
        tq_symbols={"au": "SHFE.au2406"},
        auth_user="fake",
        auth_pass="fake",
        api_factory=lambda: api,
        start_background=False,
    )
    broker = TqKqLiveBroker(market_data=md)

    md.close()
    md.close()
    broker.close()
    broker.close()

    assert api.close_calls == 1


def test_shutdown_idempotent_after_marketdata_error_contract() -> None:
    api = _FakeApi(fail_wait=True)
    md = TqKqMarketData(
        tq_symbols={"au": "SHFE.au2406"},
        auth_user="fake",
        auth_pass="fake",
        api_factory=lambda: api,
        start_background=True,
    )

    md.close()
    md.close()

    assert api.close_calls == 1
