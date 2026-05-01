from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main
from tools.inspect_run import inspect_run


def _all_files(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def test_inspect_run_is_read_only_and_has_expected_keys(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    # generate a run
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
    cfg_path = tmp_path / "plan.json"
    cfg_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rid = "rt_inspect"
    rc = run_plan_main(["--config", str(cfg_path), "--runtime-id", rid, "--clean"])
    assert rc == 0

    before = _all_files(tmp_path)

    report = inspect_run(
        runtime_id=rid,
        store_root=Path("data/store"),
        artifacts_root=Path("data/artifacts"),
        tail=2,
    )

    after = _all_files(tmp_path)
    assert before == after  # read-only guarantee

    assert report["runtime_id"] == rid
    assert "manifest" in report and "path" in report["manifest"]
    assert "plan" in report and "sha256" in report["plan"]
    assert "summaries" in report and "current" in report["summaries"]
    assert "decision" in report
    assert "stores" in report and "live" in report["stores"] and "sandbox" in report["stores"]
