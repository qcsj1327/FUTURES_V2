from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_local import main as run_local_main
from tools.inspect_run import inspect_run


def test_run_local_config_file_populates_plan_in_inspect_run(
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

    rid = "rt_cfg_local"
    rc = run_local_main(
        [
            "all",
            "--clean",
            "--runtime-id",
            rid,
            "--config",
            "plan.json",
            "--emit-plan-meta",
            "1",
            "--ticks-live",
            "2",
            "--ticks-sandbox",
            "2",
        ]
    )
    assert rc == 0

    report = inspect_run(
        runtime_id=rid,
        store_root=Path("data/store"),
        artifacts_root=Path("data/artifacts"),
        tail=2,
    )

    plan_block = report.get("plan")
    assert isinstance(plan_block, dict)

    assert isinstance(plan_block.get("sha256"), str)
    p = plan_block.get("path")
    assert isinstance(p, str)
    assert p.endswith("plan.json")

    router = plan_block.get("router")
    universe = plan_block.get("universe")
    strategies = plan_block.get("strategies")

    assert isinstance(router, dict)
    assert router.get("mode") == "priority"

    assert isinstance(universe, dict)
    assert universe.get("symbols") == ["au", "ag"]

    assert isinstance(strategies, list)
    assert strategies and isinstance(strategies[0], dict)
    assert strategies[0].get("name") == "simple_strategy"
