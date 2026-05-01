from __future__ import annotations

from pathlib import Path

import pytest

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_fs import JSONLFileDataStore
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from research.datastore_replay import replay_execution_events, summarize_execution_events


def test_replay_summary_expanded_fields_memory() -> None:
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
    rt.run_market_once()

    events = replay_execution_events(store, env="sandbox")
    assert len(events) == 2

    s = summarize_execution_events(events)
    assert s.total_events == 2
    assert s.success_count + s.failure_count == 2
    assert 0.0 <= s.success_rate <= 1.0

    assert isinstance(s.failure_reason_counts, dict)
    assert isinstance(s.event_count_by_strategy_name, dict)
    assert s.max_consecutive_failures >= 0
    assert s.filled_quantity_sum >= 0.0
    assert s.filled_quantity_mean >= 0.0
    assert s.avg_fill_price_mean >= 0.0


def test_replay_summary_expanded_fields_fs(
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

    s = summarize_execution_events(events)
    assert s.total_events == 2
    assert s.success_count + s.failure_count == 2
    assert 0.0 <= s.success_rate <= 1.0

    assert isinstance(s.failure_reason_counts, dict)
    assert isinstance(s.event_count_by_strategy_name, dict)
    assert s.max_consecutive_failures >= 0
    assert s.filled_quantity_sum >= 0.0
    assert s.filled_quantity_mean >= 0.0
    assert s.avg_fill_price_mean >= 0.0
