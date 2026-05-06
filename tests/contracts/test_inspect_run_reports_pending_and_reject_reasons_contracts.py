from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import BLOCKED_BY_PENDING_ORDER
from scripts.run_plan import main as run_plan_main
from tools.inspect_run import inspect_run


def _write_plan(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "env": "dev",
                "universe": {"symbols": ["au"]},
                "adapters": {
                    "market_data": {
                        "mode": "simulated_v2",
                        "params": {
                            "seed": 2704,
                            "start_prices": {"au": 120.0},
                            "drift": 0.0,
                            "vol": 0.0,
                        },
                    },
                    "broker": {
                        "mode": "simulated",
                        "params": {"fill_delay_ticks": 10},
                    },
                },
                "execution": {"max_pending_ticks": 20},
                "risk": {"max_position_qty_by_symbol": {"au": 10}},
                "strategies": [
                    {
                        "name": "simple_strategy",
                        "params": {},
                        "symbols": ["au"],
                        "priority": 1,
                        "weight": 1.0,
                    }
                ],
                "runtime": {"ticks_live": 4, "ticks_sandbox": 0, "default_quantity": 1.0},
                "promotion": {
                    "min_events": 1,
                    "min_success_rate_improvement": -1.0,
                    "max_consecutive_failures": 99,
                },
                "router": {"mode": "priority", "tie_breaker": "priority"},
            }
        ),
        encoding="utf-8",
    )


def test_inspect_pending_reports_count_and_reject_reasons(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "plan.json"
    _write_plan(cfg)

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_inspect", "--clean"]) == 0
    report = inspect_run(
        runtime_id="rt_inspect",
        store_root=tmp_path / "data" / "store",
        artifacts_root=tmp_path / "data" / "artifacts",
        tail=50,
    )

    assert "missing_candidate_summary" not in report["warnings"]
    assert "missing_strategy_switch_approved" in report["optional_warnings"]
    assert report["pending_orders_count"]["live"] == 1
    projection_pending = report["dashboard_projection"]["pending_orders"]["live"]
    assert projection_pending["count"] == 1
    assert projection_pending["items"][0]["status"] in {"NEW", "SUBMITTED", "PARTIAL"}
    assert report["dashboard_projection"]["positions"]["live"]["items"] == []
    reasons = {
        item["reason"]
        for item in report["top_lifecycle_reject_reasons"]["live"]
    }
    assert BLOCKED_BY_PENDING_ORDER in reasons
