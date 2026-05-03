from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_daemon import main as run_daemon_main


def test_daemon_manifest_declares_daemon_mode_and_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    rid = "rt_daemon_mode"
    cfg = tmp_path / "plan.json"
    cfg.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "env": "dev",
                "adapters": {"market_data": {"mode": "simulated_v2", "params": {"seed": 1}}},
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
    assert (
        run_daemon_main(
            [
                "--config",
                str(cfg),
                "--runtime-id",
                rid,
                "--env",
                "sandbox",
                "--max-ticks",
                "1",
                "--interval",
                "0",
                "--artifact-every",
                "1",
                "--clean",
            ]
        )
        == 0
    )

    manifests = list((tmp_path / "data" / "artifacts" / "manifests").glob(f"*{rid}*.json"))
    assert manifests
    payload = json.loads(manifests[-1].read_text(encoding="utf-8"))
    assert payload["run_mode"] == "daemon"
    assert payload["env"] == "sandbox"
    assert payload["artifacts"]["decision"] is None
    assert payload["artifacts"]["approved"] is None
    assert payload["artifacts"]["candidate_summary"] is None
