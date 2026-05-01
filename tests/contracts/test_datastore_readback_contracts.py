from __future__ import annotations

from pathlib import Path

import pytest

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_fs import JSONLFileDataStore
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory


def test_memory_datastore_readback_returns_structured_execution_event() -> None:
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

    evs = store.read_fill_events(env="sandbox")
    assert len(evs) == 1
    ev = evs[0]
    assert ev["event_type"] == "execution"
    for k in ("ts", "runtime_id", "env", "strategy_name", "success"):
        assert k in ev


def test_fs_datastore_readback_returns_structured_execution_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    cfg = RuntimeConfig()
    store = JSONLFileDataStore(
        root_dir=Path("data/store/sandbox"),
        env="sandbox",
        runtime_id=cfg.runtime_id,
    )

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

    evs = store.read_fill_events(env="sandbox")
    assert len(evs) == 1
    ev = evs[0]
    assert ev["event_type"] == "execution"
    for k in ("ts", "runtime_id", "env", "strategy_name", "success"):
        assert k in ev
