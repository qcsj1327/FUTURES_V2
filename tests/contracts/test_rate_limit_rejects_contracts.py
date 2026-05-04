from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import RATE_LIMITED
from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_rate_limited_contracts(
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
                "universe": {"symbols": ["au"]},
                "adapters": {
                    "market_data": {
                        "mode": "simulated_v2",
                        "params": {
                            "seed": 4111,
                            "start_prices": {"au": 120.0},
                            "start_volumes": {"au": 1000.0},
                            "drift": 0.0,
                            "vol": 0.0,
                        },
                    }
                },
                "execution": {"min_order_interval_ticks": 3},
                "strategies": [
                    {
                        "name": "simple_strategy",
                        "params": {},
                        "symbols": ["au"],
                        "priority": 1,
                        "weight": 1.0,
                    }
                ],
                "runtime": {
                    "mode": "simulated_v2",
                    "ticks_live": 3,
                    "ticks_sandbox": 0,
                    "default_quantity": 1.0,
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

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_rate_limit", "--clean"]) == 0

    lifecycle = _events(
        tmp_path / "data" / "store" / "live" / "rt_rate_limit" / "order_lifecycle_events.jsonl"
    )
    assert any(event.get("reason") == RATE_LIMITED for event in lifecycle)
