from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main


def test_run_plan_accepts_config_file_and_runs_end_to_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    plan = {
        "schema_version": 1,
        "env": "dev",
        "universe": {"symbols": ["au", "ag"]},
        "strategies": [
            {
                "name": "simple_strategy",
                "params": {"force_decision": "HOLD"},
                "symbols": ["au", "ag"],
                "priority": 10,
                "weight": 0.7,
            },
            {
                "name": "simple_strategy_alt",
                "params": {"force_decision": "HOLD"},
                "symbols": ["au", "ag"],
                "priority": 20,
                "weight": 0.3,
            },
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
        "router": {"mode": "netting", "tie_breaker": "priority"},
    }

    cfg_path = tmp_path / "plan.json"
    cfg_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rid = "rt_cfg"
    rc = run_plan_main(["--config", str(cfg_path), "--runtime-id", rid, "--clean"])
    assert rc == 0

    assert (tmp_path / "data" / "store" / "live" / rid).exists()
    assert (tmp_path / "data" / "store" / "sandbox" / rid).exists()

    assert (tmp_path / "data" / "artifacts" / "summaries" / f"current_{rid}.json").exists()
    assert (tmp_path / "data" / "artifacts" / "summaries" / f"candidate_{rid}.json").exists()
    assert (tmp_path / "data" / "artifacts" / "approved" / f"approved_cand_{rid}.json").exists()

    dec = tmp_path / "data" / "artifacts" / "decisions"
    man = tmp_path / "data" / "artifacts" / "manifests"
    assert len(list(dec.glob(f"decision_{rid}_*.json"))) >= 1
    assert len(list(man.glob(f"manifest_{rid}_*.json"))) >= 1
