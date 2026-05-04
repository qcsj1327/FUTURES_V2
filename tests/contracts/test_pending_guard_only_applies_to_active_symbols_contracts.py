from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import BLOCKED_BY_PENDING_ORDER
from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_pending_active_only_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "plan.json"
    cfg.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "env": "dev",
                "universe": {"symbols": ["ag", "au"]},
                "adapters": {
                    "market_data": {
                        "mode": "simulated_v2",
                        "params": {
                            "seed": 3131,
                            "start_prices": {"ag": 121.0, "au": 120.0},
                            "start_volumes": {"ag": 1100.0, "au": 1000.0},
                            "drift": 0.0,
                            "vol": 0.0,
                        },
                    },
                    "broker": {
                        "mode": "simulated",
                        "params": {
                            "fill_delay_ticks": 10,
                            "partial_fill_ratio": 1.0,
                        },
                    },
                },
                "execution": {"max_pending_ticks": 20},
                "instruments": {
                    "trading_sessions": {
                        "ag": [{"start": "08:00", "end": "08:10"}],
                        "au": [{"start": "08:00", "end": "08:10"}],
                    },
                    "roll_policy": {
                        "mode": "fixed_contract",
                        "contracts": {"ag": "ag_main", "au": "au_main"},
                    },
                },
                "strategies": [
                    {
                        "name": "simple_strategy",
                        "params": {},
                        "symbols": ["ag", "au"],
                        "priority": 1,
                        "weight": 1.0,
                    }
                ],
                "runtime": {
                    "ticks_live": 3,
                    "ticks_sandbox": 0,
                    "default_quantity": 1.0,
                    "active_top_n": 1,
                    "rank_window": 2,
                    "rank_metric": "signal_strength",
                    "rank_refresh_every": 1,
                    "rank_emit_events": 1,
                },
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

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_pr31_pending", "--clean"]) == 0

    base = tmp_path / "data" / "store" / "live" / "rt_pr31_pending"
    rank_events = _events(base / "rank_events.jsonl")
    lifecycle_events = _events(base / "order_lifecycle_events.jsonl")
    blocked = [
        event
        for event in lifecycle_events
        if event.get("reason") == BLOCKED_BY_PENDING_ORDER
    ]

    assert rank_events[-1]["active_symbols"] == ["ag"]
    assert blocked
    assert {str(event["symbol"]) for event in blocked} == {"ag"}
    assert all(str(event["symbol"]) != "au" for event in lifecycle_events)
