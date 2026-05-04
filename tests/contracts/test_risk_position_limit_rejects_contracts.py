from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import RISK_POSITION_LIMIT
from scripts.run_plan import main as run_plan_main
from web.api.events import get_run_events


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
                            "seed": 2703,
                            "start_prices": {"au": 120.0},
                            "drift": 0.0,
                            "vol": 0.0,
                        },
                    },
                    "broker": {"mode": "simulated", "params": {}},
                },
                "risk": {"max_position_qty_by_symbol": {"au": 1}},
                "strategies": [
                    {
                        "name": "simple_strategy",
                        "params": {},
                        "symbols": ["au"],
                        "priority": 1,
                        "weight": 1.0,
                    }
                ],
                "runtime": {"ticks_live": 3, "ticks_sandbox": 0, "default_quantity": 1.0},
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


def test_position_limit_rejects_without_order_or_fill_growth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "plan.json"
    _write_plan(cfg)

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_risk", "--clean"]) == 0
    base = tmp_path / "data" / "store" / "live" / "rt_risk"
    lifecycle = _events(base / "order_lifecycle_events.jsonl")
    order_events = _events(base / "order_events.jsonl")
    fill_events = _events(base / "fill_events.jsonl")

    rejected = [e for e in lifecycle if e.get("reason") == RISK_POSITION_LIMIT]
    assert len(order_events) == 1
    assert len(fill_events) == 1
    assert rejected
    assert all(e["status"] == "REJECTED" for e in rejected)
    assert all(e["instrument_id"] == "au" for e in rejected)

    api_payload = get_run_events(
        runtime_id="rt_risk",
        store_root=tmp_path / "data" / "store",
        event_type="order_lifecycle",
        tail=50,
    )
    reasons = {e.get("reason") for e in api_payload["timeline"]}
    assert RISK_POSITION_LIMIT in reasons
