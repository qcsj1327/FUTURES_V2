from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scripts.run_plan import main as run_plan_main
from web.server import app


def test_metrics_contains_reason_zh_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    plan = {
        "schema_version": 1,
        "env": "dev",
        "universe": {"symbols": ["au"]},
        "strategies": [
            {
                "name": "simple_strategy",
                "params": {"force_decision": "HOLD"},
                "symbols": ["au"],
                "priority": 10,
                "weight": 1.0,
            }
        ],
        "runtime": {"ticks_live": 2, "ticks_sandbox": 2, "default_quantity": 1.0},
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "priority", "tie_breaker": "priority"},
    }
    cfg = tmp_path / "plan.json"
    cfg.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rid = "rt_metrics_zh"
    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    client = TestClient(app)
    r = client.get(f"/runs/{rid}/metrics")
    assert r.status_code == 200

    payload = r.json()
    cur = payload["current"]
    summary = cur.get("summary")
    assert isinstance(summary, dict)

    # zh fields must exist (even if empty)
    assert "failure_reason_counts_zh" in summary
    assert "top_failure_reasons_zh" in summary

    assert isinstance(summary["failure_reason_counts_zh"], dict)
    assert isinstance(summary["top_failure_reasons_zh"], list)
