from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.loader import load_plan


def test_loader_rejects_unknown_root_key(tmp_path: Path) -> None:
    plan = {
        "schema_version": 1,
        "env": "dev",
        "universe": {"symbols": ["au"]},
        "strategies": [],
        "runtime": {"ticks_live": 1, "ticks_sandbox": 1, "default_quantity": 1.0},
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "priority", "tie_breaker": "priority"},
        "oops": 123,
    }
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError):
        _ = load_plan(p, runtime_id="rt_x")


def test_loader_rejects_invalid_router_mode(tmp_path: Path) -> None:
    plan = {
        "schema_version": 1,
        "env": "dev",
        "universe": {"symbols": ["au"]},
        "strategies": [],
        "runtime": {"ticks_live": 1, "ticks_sandbox": 1, "default_quantity": 1.0},
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "bad_mode", "tie_breaker": "priority"},
    }
    p = tmp_path / "plan.json"
    p.write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError):
        _ = load_plan(p, runtime_id="rt_x")
