from __future__ import annotations

from adapters.broker.tqkq_live_broker import TqKqLiveBroker
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig


class _FakeMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=120.0, volume=1000.0, ts=1)


class _FakeApi:
    def get_account(self) -> object:
        return {
            "cash": 880000.0,
            "equity": 900000.0,
            "margin_used": 20000.0,
        }

    def get_position(self) -> list[object]:
        return [{"symbol": "SHFE.au2406", "quantity": 2.0}]


def test_portfolio_sync_updates_metrics_contracts() -> None:
    store = MemoryDataStore(env="live", runtime_id="rt_portfolio_sync")
    market_data = _FakeMarketData()
    broker = TqKqLiveBroker(
        market_data=market_data,
        api_factory=lambda: _FakeApi(),
        dry_run=True,
    )
    runtime = Runtime(
        config=RuntimeConfig(runtime_id="rt_portfolio_sync"),
        market_data=market_data,
        broker=broker,
        datastore=store,
        runtime_id="rt_portfolio_sync",
    )

    runtime._maybe_save_snapshot()

    portfolio = store.load_latest_portfolio_snapshot(env="live")
    assert portfolio is not None
    metadata = portfolio.metadata
    assert portfolio.equity == 900000.0
    assert portfolio.cash == 880000.0
    assert metadata["margin_used"] == 20000.0
    assert metadata["risk_ratio"] == 20000.0 / 900000.0
    assert metadata["portfolio_sync"] == {
        "source": "tqkq_live",
        "positions_qty_by_symbol": {"au": 2.0},
        "cash": 880000.0,
        "equity": 900000.0,
        "margin_used": 20000.0,
    }
