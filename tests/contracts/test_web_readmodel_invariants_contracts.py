from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main
from web.api.runs import get_latest_run


def test_web_detail_invariants_router_and_plan_sha(
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

    rid = "rt_web_inv"
    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    detail = get_latest_run(runtime_id=rid, artifacts_root=Path("data/artifacts"))

    assert detail["runtime_id"] == rid
    assert detail["router_mode"] == "priority"
    assert detail["router_mode_zh"] != "未知路由"
    assert detail["plan"]["sha256"]
    assert isinstance(detail["reasons_zh"], list)

    cfg2 = detail["plan"]["config"]
    assert isinstance(cfg2, dict)
    router = cfg2.get("router")
    assert isinstance(router, dict)
    assert router.get("mode") == detail["router_mode"]
