from __future__ import annotations

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory


def test_execution_event_schema_has_required_fields() -> None:
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

    rt.run_market_once()

    assert len(store.fill_events) == 1
    ev = store.fill_events[0]
    assert isinstance(ev, dict)
    assert ev["event_type"] == "execution"

    for k in ("ts", "runtime_id", "env", "strategy_name", "success"):
        assert k in ev
