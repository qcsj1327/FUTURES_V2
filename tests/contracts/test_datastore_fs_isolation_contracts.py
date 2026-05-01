from __future__ import annotations

from pathlib import Path

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_fs import JSONLFileDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory


def test_fs_datastore_isolation_live_not_touched_by_sandbox(tmp_path: Path) -> None:
    config = RuntimeConfig()

    md = SimulatedMarketData()
    broker = SimulatedBroker(md)

    live_store = JSONLFileDataStore(
        root_dir=tmp_path / "live",
        env="live",
        runtime_id=config.runtime_id,
    )
    live_runtime = RuntimeFactory.build_live_runtime(
        config=config,
        market_data=md,
        broker=broker,
        datastore=live_store,
    )

    sandbox_store = JSONLFileDataStore(
        root_dir=tmp_path / "sandbox",
        env="sandbox",
        runtime_id=config.runtime_id,
    )
    sandbox_runtime = RuntimeFactory.build_sandbox_runtime_from_live(
        live_runtime,
        datastore=sandbox_store,
    )

    sandbox_runtime.run_market_once()

    live_snap = tmp_path / "live" / config.runtime_id / "portfolio_snapshots.jsonl"
    sandbox_snap = tmp_path / "sandbox" / config.runtime_id / "portfolio_snapshots.jsonl"

    # sandbox write must not create/touch live files
    assert not live_snap.exists()
    assert sandbox_snap.exists()
    assert sandbox_snap.read_text(encoding="utf-8").strip() != ""
