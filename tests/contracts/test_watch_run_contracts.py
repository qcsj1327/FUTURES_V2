from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main
from tools.watch_run import main as watch_main


def _all_files(root: Path) -> set[str]:
    return {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()}


def test_watch_run_is_read_only_and_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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
    cfg_path = tmp_path / "plan.json"
    cfg_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rid = "rt_watch"
    rc = run_plan_main(["--config", str(cfg_path), "--runtime-id", rid, "--clean"])
    assert rc == 0

    before = _all_files(tmp_path)

    # run watch 2 iterations with interval=0 (fast)
    rc2 = watch_main([rid, "--interval", "0", "--count", "2"])
    assert rc2 == 0

    after = _all_files(tmp_path)
    assert before == after  # read-only guarantee

    out = capsys.readouterr().out
    assert "rid=rt_watch" in out
