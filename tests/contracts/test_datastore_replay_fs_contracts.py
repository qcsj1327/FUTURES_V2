from __future__ import annotations

from pathlib import Path

import pytest

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_fs import JSONLFileDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from research.datastore_replay import replay_execution_events, summarize_execution_events


def test_fs_datastore_replay_orders_by_ts_and_summarizes(
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
    rt.run_market_once()

    events = replay_execution_events(store, env="sandbox")
    assert len(events) == 2
    assert events[0]["ts"] <= events[1]["ts"]

    summary = summarize_execution_events(events)
    assert summary.total_events == 2
    assert summary.success_count + summary.failure_count == 2
    assert 0.0 <= summary.success_rate <= 1.0
