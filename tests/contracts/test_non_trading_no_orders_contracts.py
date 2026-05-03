from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main


def test_non_trading_time_produces_no_order_or_fill_events(
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
                "adapters": {
                    "market_data": {
                        "mode": "simulated_v2",
                        "params": {
                            "seed": 1,
                            "start_prices": {"au": 450.0},
                            "start_volumes": {"au": 1000.0},
                        },
                    }
                },
                "universe": {"symbols": ["au"]},
                "strategies": [
                    {
                        "name": "simple_strategy",
                        "params": {},
                        "symbols": ["au"],
                        "priority": 1,
                        "weight": 1.0,
                    }
                ],
                "instruments": {
                    "trading_sessions": {
                        "au": [{"start": "09:00", "end": "15:00"}]
                    },
                    "roll_policy": {
                        "mode": "fixed_contract",
                        "contracts": {"au": "SHFE.au2406"},
                    },
                },
                "runtime": {"ticks_live": 1, "ticks_sandbox": 1, "default_quantity": 1.0},
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

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_closed", "--clean"]) == 0

    for env in ("live", "sandbox"):
        store_dir = tmp_path / "data" / "store" / env / "rt_closed"
        assert not (store_dir / "order_events.jsonl").exists()
        assert not (store_dir / "fill_events.jsonl").exists()
