from __future__ import annotations

import json
from pathlib import Path

import pytest

from config.loader import load_plan


def test_tqkq_sim_broker_requires_tqkq_marketdata(tmp_path: Path) -> None:
    cfg = tmp_path / "plan.json"
    cfg.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "env": "dev",
                "adapters": {
                    "market_data": {"mode": "simulated_v2", "params": {"seed": 1}},
                    "broker": {"mode": "tqkq_sim"},
                },
                "universe": {"symbols": ["au"]},
                "strategies": [
                    {
                        "name": "simple_strategy",
                        "params": {"force_decision": "HOLD"},
                        "symbols": ["au"],
                        "priority": 1,
                        "weight": 1.0,
                    }
                ],
                "instruments": {
                    "roll_policy": {
                        "mode": "fixed_contract",
                        "contracts": {"au": "SHFE.au2406"},
                    }
                },
                "runtime": {"ticks_live": 1, "ticks_sandbox": 0, "default_quantity": 1.0},
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

    with pytest.raises(ValueError, match="tqkq_sim requires adapters.market_data.mode=tqkq"):
        load_plan(cfg, runtime_id="rt_bad_broker_mode")

