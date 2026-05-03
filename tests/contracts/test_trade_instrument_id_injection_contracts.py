from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from scripts.run_plan import main as run_plan_main


def _ts(value: str) -> int:
    dt = datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("Asia/Shanghai"))
    return int(dt.timestamp())


def test_execution_order_trade_instrument_id_comes_from_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    prices = tmp_path / "prices.json"
    prices.write_text(
        json.dumps({"au": {"price": 450.0, "volume": 1000.0, "ts": _ts("2026-05-04T10:00:00")}}),
        encoding="utf-8",
    )
    cfg = tmp_path / "plan.json"
    cfg.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "env": "dev",
                "adapters": {"market_data": {"mode": "live_file", "prices_path": str(prices)}},
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

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_trade_id", "--clean"]) == 0

    order_path = tmp_path / "data" / "store" / "live" / "rt_trade_id" / "order_events.jsonl"
    lines = order_path.read_text(encoding="utf-8").splitlines()
    assert lines
    first = json.loads(lines[0])
    assert first["instrument_id"] == "au"
    assert first["trade_instrument_id"] == "SHFE.au2406"
