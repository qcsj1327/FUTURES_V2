from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.loader import load_plan


def test_loader_resolves_datastore_paths_relative_to_plan_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other = tmp_path / "other_cwd"
    other.mkdir(parents=True, exist_ok=True)
    monkeypatch.chdir(other)

    plan_dir = tmp_path / "plan_dir"
    plan_dir.mkdir()

    plan = {
        "schema_version": 1,
        "env": "dev",
        "datastore": {
            "store_root": "out/store",
            "artifacts_root": "out/artifacts",
            "approved_dir": "out/artifacts/approved",
            "decisions_dir": "out/artifacts/decisions",
            "summaries_dir": "out/artifacts/summaries",
            "manifests_dir": "out/artifacts/manifests",
        },
        "universe": {"symbols": ["au"]},
        "strategies": [
            {
            "name": "simple_strategy",
            "params": {},
            "symbols": ["au"],
            "priority": 10,
            "weight": 1.0,
        },
        ],
        "runtime": {"ticks_live": 1, "ticks_sandbox": 1, "default_quantity": 1.0},
        "promotion": {
        "min_events": 1,
        "min_success_rate_improvement": -1.0,
        "max_consecutive_failures": 99,
    },
        "router": {"mode": "priority", "tie_breaker": "priority"},
    }

    p = plan_dir / "plan.json"
    p.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    loaded = load_plan(p, runtime_id="rt_rel")

    assert loaded.datastore.store_root.resolve() == (plan_dir / "out" / "store").resolve()
    assert loaded.datastore.artifacts_root.resolve() == (plan_dir / "out" / "artifacts").resolve()
    assert (
        loaded.datastore.manifests_dir.resolve()
        == (plan_dir / "out" / "artifacts" / "manifests").resolve()
    )


def test_loader_resolves_live_file_prices_path_relative_to_plan_dir(tmp_path: Path) -> None:
    plan_dir = tmp_path / "plan_dir"
    plan_dir.mkdir()
    (plan_dir / "prices.json").write_text('{"au": 100.0}', encoding="utf-8")

    plan = {
        "schema_version": 1,
        "env": "dev",
        "adapters": {"market_data": {"mode": "live_file", "prices_path": "prices.json"}},
        "universe": {"symbols": ["au"]},
        "strategies": [
            {
            "name": "simple_strategy",
            "params": {},
            "symbols": ["au"],
            "priority": 10,
            "weight": 1.0,
        },
        ],
        "runtime": {"ticks_live": 1, "ticks_sandbox": 1, "default_quantity": 1.0},
        "promotion": {
        "min_events": 1,
        "min_success_rate_improvement": -1.0,
        "max_consecutive_failures": 99,
    },
        "router": {"mode": "priority", "tie_breaker": "priority"},
    }

    p = plan_dir / "plan.json"
    p.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    loaded = load_plan(p, runtime_id="rt_prices")
    assert loaded.adapters.market_data.prices_path is not None
    assert (
        Path(loaded.adapters.market_data.prices_path).resolve()
        == (plan_dir / "prices.json").resolve()
    )
