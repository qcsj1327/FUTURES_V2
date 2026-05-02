from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scripts.run_plan import main as run_plan_main
from web.server import app


def test_fastapi_health_and_runs_routes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    # generate one run
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
        "runtime": {"ticks_live": 1, "ticks_sandbox": 1, "default_quantity": 1.0},
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "priority", "tie_breaker": "priority"},
    }
    cfg = tmp_path / "plan.json"
    cfg.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rid = "rt_api"
    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    client = TestClient(app)

    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True

    r2 = client.get("/runs?limit=10&offset=0")
    assert r2.status_code == 200
    rows = r2.json()
    assert any(x["runtime_id"] == rid for x in rows)

    r3 = client.get(f"/runs/{rid}")
    assert r3.status_code == 200
    detail = r3.json()
    assert detail["runtime_id"] == rid

    r4 = client.get(f"/runs/{rid}/manifest")
    assert r4.status_code == 200
    assert r4.json().get("runtime_id") == rid


def test_fastapi_runs_query_filtering(
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
        "runtime": {"ticks_live": 1, "ticks_sandbox": 1, "default_quantity": 1.0},
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "priority", "tie_breaker": "priority"},
    }
    cfg = tmp_path / "plan.json"
    cfg.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_aaa", "--clean"]) == 0
    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_bbb"]) == 0

    client = TestClient(app)
    r = client.get("/runs?q=rt_bbb")
    assert r.status_code == 200
    rows = r.json()
    assert all(x["runtime_id"] == "rt_bbb" for x in rows)
