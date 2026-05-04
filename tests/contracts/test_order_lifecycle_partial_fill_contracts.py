from __future__ import annotations

import json
from pathlib import Path

import pytest

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
                            "seed": 2601,
                            "start_prices": {"au": 120.0},
                            "drift": 0.0,
                            "vol": 0.0,
                        },
                    },
                    "broker": {
                        "mode": "simulated",
                        "params": {
                            "fill_delay_ticks": 1,
                            "partial_fill_ratio": 0.5,
                            "max_partial_steps": 1,
                        },
                    },
                },
                "execution": {"max_pending_ticks": 10},
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


def test_order_lifecycle_v2_partial_fill_sequence_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "plan.json"
    _write_plan(cfg)

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_partial", "--clean"]) == 0
    path = tmp_path / "data" / "store" / "live" / "rt_partial" / "order_lifecycle_events.jsonl"
    events = _events(path)
    first_order_id = str(events[0]["order_id"])
    statuses = [str(e["status"]) for e in events if e["order_id"] == first_order_id]
    assert statuses == ["NEW", "SUBMITTED", "PARTIAL", "FILLED"]
    assert [str(e["reason"]) for e in events if e["order_id"] == first_order_id][-2:] == [
        "simulated_partial_fill",
        "simulated_fill",
    ]
