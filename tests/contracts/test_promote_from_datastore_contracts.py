from __future__ import annotations

from pathlib import Path

import pytest

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_fs import JSONLFileDataStore
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from optimize.promoter.promote_from_datastore import promote_from_datastore
from optimize.promoter.promotion_gate import PromotionThresholds


def _run_ticks_memory(*, env: str, n: int) -> MemoryDataStore:
    cfg = RuntimeConfig()
    store = MemoryDataStore(env=env, runtime_id=cfg.runtime_id)

    md = SimulatedMarketData()
    broker = SimulatedBroker(md)
    rt = RuntimeFactory.build_runtime(
        config=cfg,
        market_data=md,
        broker=broker,
        environment=env,
        datastore=store,
    )
    for _ in range(n):
        rt.run_market_once()
    return store


def test_promote_from_datastore_memory_rejects_when_insufficient_events() -> None:
    current_store = _run_ticks_memory(env="live", n=5)
    candidate_store = _run_ticks_memory(env="sandbox", n=2)

    decision = promote_from_datastore(
        current_store=current_store,
        current_env="live",
        candidate_store=candidate_store,
        candidate_env="sandbox",
        thresholds=PromotionThresholds(
            min_events=5,
            min_success_rate_improvement=0.0,
            max_consecutive_failures=99,
        ),
    )
    assert decision.approved is False
    assert "insufficient_events" in decision.reasons


def test_promote_from_datastore_fs_smoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    cfg = RuntimeConfig()
    md = SimulatedMarketData()
    broker = SimulatedBroker(md)

    cur_store = JSONLFileDataStore(
        root_dir=Path("data/store/live"),
        env="live",
        runtime_id=cfg.runtime_id,
    )
    cand_store = JSONLFileDataStore(
        root_dir=Path("data/store/sandbox"),
        env="sandbox",
        runtime_id=cfg.runtime_id,
    )

    cur_rt = RuntimeFactory.build_runtime(
        config=cfg,
        market_data=md,
        broker=broker,
        environment="live",
        datastore=cur_store,
    )
    cand_rt = RuntimeFactory.build_runtime(
        config=cfg,
        market_data=md,
        broker=broker,
        environment="sandbox",
        datastore=cand_store,
    )

    cur_rt.run_market_once()
    cur_rt.run_market_once()
    cand_rt.run_market_once()
    cand_rt.run_market_once()

    decision = promote_from_datastore(
        current_store=cur_store,
        current_env="live",
        candidate_store=cand_store,
        candidate_env="sandbox",
        thresholds=PromotionThresholds(
            min_events=2,
            min_success_rate_improvement=0.0,
            max_consecutive_failures=99,
        ),
    )

    # only asserts that the pipeline runs end-to-end (approval depends on success_rate delta)
    assert isinstance(decision.approved, bool)
    assert isinstance(decision.reasons, list)
