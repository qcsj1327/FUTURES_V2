from __future__ import annotations

from typing import Any

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory


class SpyMemoryDataStore(MemoryDataStore):
    def __init__(self, *, env: str, runtime_id: str) -> None:
        super().__init__(env=env, runtime_id=runtime_id)
        self.load_calls = 0

    def load_latest_portfolio_snapshot(self, *, env: str) -> Any | None:
        self.load_calls += 1
        return super().load_latest_portfolio_snapshot(env=env)


def test_sandbox_build_prefers_live_datastore_snapshot_call() -> None:
    config = RuntimeConfig()
    md = SimulatedMarketData()
    broker = SimulatedBroker(md)

    live_store = SpyMemoryDataStore(env="live", runtime_id=config.runtime_id)
    live = RuntimeFactory.build_live_runtime(
        config=config,
        market_data=md,
        broker=broker,
        datastore=live_store,
    )

    # ensure there is a snapshot available in the live store
    live.run_market_once()
    assert len(live_store.snapshots) >= 1

    sandbox_store = MemoryDataStore(env="sandbox", runtime_id=config.runtime_id)
    _ = RuntimeFactory.build_sandbox_runtime_from_live(live, datastore=sandbox_store)

    assert live_store.load_calls >= 1
