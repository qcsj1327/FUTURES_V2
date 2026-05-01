from __future__ import annotations

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from research.datastore_replay import replay_execution_events, summarize_execution_events


def test_datastore_replay_orders_by_ts_and_summarizes() -> None:
    cfg = RuntimeConfig()
    store = MemoryDataStore(env="sandbox", runtime_id=cfg.runtime_id)

    md = SimulatedMarketData()
    broker = SimulatedBroker(md)

    rt = RuntimeFactory.build_runtime(
        config=cfg,
        market_data=md,
        broker=broker,
        environment="sandbox",
        datastore=store,
    )

    # run multiple ticks so ordering is meaningful
    rt.run_market_once()
    rt.run_market_once()

    events = replay_execution_events(store, env="sandbox")
    assert len(events) == 2
    assert events[0]["ts"] <= events[1]["ts"]

    summary = summarize_execution_events(events)
    assert summary.total_events == 2
    assert summary.success_count + summary.failure_count == 2
    assert 0.0 <= summary.success_rate <= 1.0
