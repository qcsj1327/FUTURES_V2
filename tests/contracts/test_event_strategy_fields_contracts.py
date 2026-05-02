from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main


def test_events_use_config_strategy_id_and_have_impl(
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
                "params": {},
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

    rid = "rt_strategy_fields"
    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    p = tmp_path / "data" / "store" / "live" / rid / "fill_events.jsonl"
    assert p.exists()

    allowed_ids = {"simple_strategy", "exit", "main"}

    for line in p.read_text(encoding="utf-8").splitlines():
        ev = json.loads(line)
        assert ev.get("strategy_id") == ev.get("strategy_name")
        assert ev["strategy_id"] in allowed_ids
        assert ev["strategy_id"] != "simple_trend"
        assert isinstance(ev.get("strategy_impl"), str)
        assert ev["strategy_impl"]
