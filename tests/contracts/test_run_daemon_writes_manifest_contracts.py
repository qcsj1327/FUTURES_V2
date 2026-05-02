from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_daemon import main as run_daemon_main
from tools.inspect_run import inspect_run


def test_run_daemon_writes_manifest_so_inspect_run_works(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    # Minimal plan with datastore rooted under tmp_path
    store_root = tmp_path / "data" / "store"
    artifacts_root = tmp_path / "data" / "artifacts"

    plan = {
        "schema_version": 1,
        "env": "dev",
        "datastore": {
            "store_root": str(store_root),
            "artifacts_root": str(artifacts_root),
            "approved_dir": str(artifacts_root / "approved"),
            "decisions_dir": str(artifacts_root / "decisions"),
            "summaries_dir": str(artifacts_root / "summaries"),
            "manifests_dir": str(artifacts_root / "manifests"),
        },
        "adapters": {
            "market_data": {
                "mode": "simulated_v2",
                "params": {"seed": 1, "vol": 0.01},
            }
        },
        "universe": {"symbols": ["au"]},
        "strategies": [
            {
                "name": "simple_strategy",
                "params": {},
                "symbols": ["au"],
                "priority": 10,
                "weight": 1.0,
            }
        ],
        "runtime": {"ticks_live": 1, "ticks_sandbox": 1, "default_quantity": 1.0},
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "priority", "tie_breaker": "priority"},
    }

    cfg = tmp_path / "plan.json"
    cfg.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rid = "rt_daemon_test"
    rc = run_daemon_main(
        [
            "--config",
            str(cfg),
            "--runtime-id",
            rid,
            "--env",
            "sandbox",
            "--max-ticks",
            "1",
            "--interval",
            "0.0",
            "--clean",
        ]
    )
    assert rc == 0

    # inspect_run should not raise (manifest must exist)
    report = inspect_run(
        runtime_id=rid,
        store_root=store_root,
        artifacts_root=artifacts_root,
        tail=2,
    )
    assert report["runtime_id"] == rid
    assert isinstance(report.get("manifest"), dict)
