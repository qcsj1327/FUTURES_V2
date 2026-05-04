from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.run_plan import main as run_plan_main


def test_specs_snapshot_is_written_for_run_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    rid = "rt_specs_snapshot"
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
                        "params": {"force_decision": "HOLD"},
                        "symbols": ["au"],
                        "priority": 1,
                        "weight": 1.0,
                    }
                ],
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

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    snap_path = tmp_path / "data" / "artifacts" / "specs" / f"specs_{rid}.json"
    assert snap_path.exists()
    payload: dict[str, Any] = json.loads(snap_path.read_text(encoding="utf-8"))
    assert payload["runtime_id"] == rid
    specs = payload.get("specs")
    assert isinstance(specs, dict)
    assert "au" in specs
    for key in (
        "tick_size",
        "multiplier",
        "margin_rate",
        "commission_model",
        "slippage_model",
        "min_qty",
    ):
        assert key in specs["au"]

