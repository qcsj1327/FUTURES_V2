from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main


def test_run_plan_with_live_file_marketdata_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"au": 100.0, "ag": 50.0}), encoding="utf-8")

    plan = {
        "schema_version": 1,
        "env": "dev",
        "adapters": {"market_data": {"mode": "live_file", "prices_path": str(prices)}},
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

    rid = "rt_live_file"
    rc = run_plan_main(["--config", str(cfg_path), "--runtime-id", rid, "--clean"])
    assert rc == 0

    assert (tmp_path / "data" / "store" / "live" / rid).exists()
    assert (tmp_path / "data" / "store" / "sandbox" / rid).exists()
