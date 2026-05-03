from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main


def _plan(path: Path) -> None:
    path.write_text(
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


def test_clean_only_removes_current_runtime_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = tmp_path / "plan.json"
    _plan(cfg)

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_keep", "--clean"]) == 0
    keep_manifests = set((tmp_path / "data" / "artifacts" / "manifests").glob("*rt_keep*.json"))
    assert keep_manifests

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_clean", "--clean"]) == 0
    assert all(p.exists() for p in keep_manifests)
