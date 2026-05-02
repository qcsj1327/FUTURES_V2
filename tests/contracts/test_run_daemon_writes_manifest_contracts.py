from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_daemon import main as run_daemon_main


def test_run_daemon_writes_manifest_and_summaries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    rid = "rt_daemon_test"

    plan = {
        "schema_version": 1,
        "env": "dev",
        "datastore": {
            "store_root": "data/store",
            "artifacts_root": "data/artifacts",
            "approved_dir": "data/artifacts/approved",
            "decisions_dir": "data/artifacts/decisions",
            "summaries_dir": "data/artifacts/summaries",
            "manifests_dir": "data/artifacts/manifests",
        },
        "adapters": {"market_data": {"mode": "simulated_v2", "params": {"seed": 1, "vol": 0.01}}},
        "universe": {"symbols": ["au", "ag"]},
        "strategies": [
            {
                "name": "simple_strategy",
                "params": {"force_decision": "HOLD"},
                "symbols": ["au", "ag"],
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

    rc = run_daemon_main(
        [
            "--config",
            str(cfg),
            "--runtime-id",
            rid,
            "--env",
            "sandbox",
            "--max-ticks",
            "3",
            "--interval",
            "0.0",
            "--artifact-every",
            "1",
            "--clean",
        ]
    )
    assert rc == 0

    mdir = tmp_path / "data" / "artifacts" / "manifests"
    manifests = list(mdir.glob(f"manifest_{rid}_*.json"))
    assert manifests, "daemon must create at least one manifest for inspect_run"

    sdir = tmp_path / "data" / "artifacts" / "summaries"
    assert (sdir / f"current_{rid}.json").exists()
    assert (sdir / f"candidate_{rid}.json").exists()
