from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main


def test_run_plan_produces_orchestrated_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    plan = {
        "schema_version": 1,
        "env": "dev",
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
        "runtime": {"ticks_live": 2, "ticks_sandbox": 2, "default_quantity": 1.0},
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
            "write_summary": True,
            "write_decision": True,
            "write_manifest": True,
            "write_approved": True,
        },
        "router": {"mode": "priority", "tie_breaker": "priority"},
        "datastore": {
            "store_root": str(tmp_path / "data" / "store"),
            "artifacts_root": str(tmp_path / "data" / "artifacts"),
            "approved_dir": str(tmp_path / "data" / "artifacts" / "approved"),
            "decisions_dir": str(tmp_path / "data" / "artifacts" / "decisions"),
            "summaries_dir": str(tmp_path / "data" / "artifacts" / "summaries"),
            "manifests_dir": str(tmp_path / "data" / "artifacts" / "manifests"),
        },
    }
    cfg = tmp_path / "plan.json"
    cfg.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rid = "rt_orch_runplan"
    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    # store dirs exist
    assert (tmp_path / "data" / "store" / "live" / rid).exists()
    assert (tmp_path / "data" / "store" / "sandbox" / rid).exists()

    # artifacts exist
    assert (tmp_path / "data" / "artifacts" / "summaries" / f"current_{rid}.json").exists()
    assert (tmp_path / "data" / "artifacts" / "summaries" / f"candidate_{rid}.json").exists()
    assert (tmp_path / "data" / "artifacts" / "approved" / f"approved_cand_{rid}.json").exists()

    # decision + manifest are timestamped
    decisions = list((tmp_path / "data" / "artifacts" / "decisions").glob(
        f"decision_{rid}_*.json"
    ))
    assert len(decisions) >= 1
    manifests = list((tmp_path / "data" / "artifacts" / "manifests").glob(
        f"manifest_{rid}_*.json"
    ))
    assert len(manifests) >= 1
