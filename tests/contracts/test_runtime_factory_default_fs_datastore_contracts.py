from __future__ import annotations

from pathlib import Path

import pytest

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_fs import JSONLFileDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory


def test_factory_defaults_to_fs_datastore_and_keeps_live_clean(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # ensure default Path("data/store") lands under tmp_path
    monkeypatch.chdir(tmp_path)

    config = RuntimeConfig()
    md = SimulatedMarketData()
    broker = SimulatedBroker(md)

    live_runtime = RuntimeFactory.build_live_runtime(
        config=config,
        market_data=md,
        broker=broker,
    )
    assert isinstance(live_runtime.datastore, JSONLFileDataStore)
    assert live_runtime.environment == "live"
    assert live_runtime.datastore.env == "live"

    sandbox_runtime = RuntimeFactory.build_sandbox_runtime_from_live(live_runtime)
    assert isinstance(sandbox_runtime.datastore, JSONLFileDataStore)
    assert sandbox_runtime.environment == "sandbox"
    assert sandbox_runtime.datastore.env == "sandbox"

    sandbox_runtime.run_market_once()

    live_snap = (
        tmp_path
        / "data"
        / "store"
        / "live"
        / config.runtime_id
        / "portfolio_snapshots.jsonl"
    )
    sandbox_snap = (
        tmp_path
        / "data"
        / "store"
        / "sandbox"
        / config.runtime_id
        / "portfolio_snapshots.jsonl"
    )

    assert not live_snap.exists()
    assert sandbox_snap.exists()
    assert sandbox_snap.read_text(encoding="utf-8").strip() != ""
