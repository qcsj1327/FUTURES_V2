from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.run_plan import main as run_plan_main


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_cost_model_uses_registry_spec_overrides_for_tick_and_multiplier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    rid = "rt_cost_override"
    cfg = tmp_path / "plan.json"
    cfg.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "env": "dev",
                "universe": {"symbols": ["au"]},
                "strategies": [
                    {
                        "name": "simple_strategy",
                        "params": {"force_decision": "OPEN_LONG"},
                        "symbols": ["au"],
                        "priority": 10,
                        "weight": 1.0,
                    }
                ],
                "runtime": {"ticks_live": 1, "ticks_sandbox": 0, "default_quantity": 1.0},
                "instruments": {
                    "specs": {
                        "au": {
                            "tick_size": 0.2,
                            "multiplier": 10.0,
                            "commission_model": {"mode": "fixed_per_order", "value": 0.0},
                            "slippage_model": {"mode": "ticks", "value": 1.0},
                        }
                    },
                    "roll_policy": {"mode": "fixed_contract", "contracts": {"au": "SHFE.au2406"}},
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

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    fill_path = tmp_path / "data" / "store" / "live" / rid / "fill_events.jsonl"
    fills = _read_jsonl(fill_path)
    assert fills
    ev = fills[-1]
    assert ev.get("multiplier") == 10.0
    assert ev.get("tick_size") == 0.2
    # tick alignment is applied after slippage; ensure a valid multiple of tick_size.
    price = ev.get("avg_fill_price")
    assert isinstance(price, (int, float))
    assert round(float(price) / 0.2) == float(price) / 0.2

