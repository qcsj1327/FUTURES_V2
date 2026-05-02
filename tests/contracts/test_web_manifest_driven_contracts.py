from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main
from web.readmodel.loader import load_run_from_manifest
from web.readmodel.repository import FileRepository


def test_readmodel_fails_if_manifest_points_to_missing_artifact(
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
                "weight": 1.0,
            }
        ],
        "runtime": {"ticks_live": 2, "ticks_sandbox": 2, "default_quantity": 1.0},
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "priority", "tie_breaker": "priority"},
    }
    cfg = tmp_path / "plan.json"
    cfg.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rid = "rt_manifest"
    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    repo = FileRepository(artifacts_root=Path("data/artifacts"))
    mp = repo.latest_manifest_for_runtime(rid)
    assert mp is not None

    m = repo.read_json(mp)
    artifacts = m.get("artifacts")
    assert isinstance(artifacts, dict)

    # poison the manifest: point current_summary to a missing file
    artifacts["current_summary"] = str(tmp_path / "missing_current.json")
    m["artifacts"] = artifacts
    mp.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        _ = load_run_from_manifest(repo, mp)
