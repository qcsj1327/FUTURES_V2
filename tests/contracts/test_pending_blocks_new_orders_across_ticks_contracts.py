from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import BLOCKED_BY_PENDING_ORDER
from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


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
                            "seed": 2702,
                            "start_prices": {"au": 120.0},
                            "drift": 0.0,
                            "vol": 0.0,
                        },
                    },
                    "broker": {
                        "mode": "simulated",
                        "params": {"fill_delay_ticks": 5},
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


def test_pending_blocks_new_orders_across_ticks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "plan.json"
    _write_plan(cfg)

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_pending", "--clean"]) == 0
    base = tmp_path / "data" / "store" / "live" / "rt_pending"
    lifecycle = _events(base / "order_lifecycle_events.jsonl")
    order_events = _events(base / "order_events.jsonl")

    submitted = [e for e in lifecycle if e.get("status") == "SUBMITTED"]
    blocked = [e for e in lifecycle if e.get("reason") == BLOCKED_BY_PENDING_ORDER]

    assert len(submitted) == 1
    assert len(order_events) == 1
    assert len(blocked) >= 2
    assert all(e["status"] == "REJECTED" for e in blocked)
    assert all(e["trade_instrument_id"] == "au_main" for e in blocked)
