from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main


def test_manifest_contains_plan_metadata_when_config_file_used(
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

    rid = "rt_plan_meta"
    rc = run_plan_main(["--config", str(cfg_path), "--runtime-id", rid, "--clean"])
    assert rc == 0

    mdir = tmp_path / "data" / "artifacts" / "manifests"
    files = list(mdir.glob(f"manifest_{rid}_*.json"))
    assert len(files) >= 1

    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["kind"] == "promotion_manifest"
    assert payload["runtime_id"] == rid

    plan_meta = payload["plan"]
    assert plan_meta["sha256"] is not None
    assert isinstance(plan_meta["sha256"], str)
    assert len(plan_meta["sha256"]) == 64
    assert plan_meta["path"] == str(cfg_path)
    assert plan_meta["config"]["schema_version"] == 1
