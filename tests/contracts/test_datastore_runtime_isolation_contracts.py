from __future__ import annotations

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory


def test_sandbox_runtime_writes_do_not_touch_live_store() -> None:
    config = RuntimeConfig()

    live_md = SimulatedMarketData()
    live_broker = SimulatedBroker(live_md)
    live_store = MemoryDataStore(env="live", runtime_id=config.runtime_id)

    live_runtime = RuntimeFactory.build_live_runtime(
        config=config,
        market_data=live_md,
        broker=live_broker,
        datastore=live_store,
    )

    baseline_live = len(live_store.snapshots)

    sandbox_store = MemoryDataStore(env="sandbox", runtime_id=config.runtime_id)
    sandbox_runtime = RuntimeFactory.build_sandbox_runtime_from_live(
        live_runtime,
        datastore=sandbox_store,
    )

    sandbox_runtime.run_market_once()

    assert len(live_store.snapshots) == baseline_live
    assert len(sandbox_store.snapshots) == 1
    # fill_events must be written only to sandbox store (stable even if strategy produces no order)
    assert len(live_store.fill_events) == 0
    assert len(sandbox_store.fill_events) == 1
    fill = sandbox_store.fill_events[0]
    assert isinstance(fill, dict)
    assert fill.get("event_type") == "execution"
    for k in ("ts", "runtime_id", "env", "strategy_name", "success"):
        assert k in fill

