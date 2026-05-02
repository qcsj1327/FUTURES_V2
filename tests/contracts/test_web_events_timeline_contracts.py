from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scripts.run_plan import main as run_plan_main
from web.server import app


def test_events_timeline_is_sorted_and_annotated(
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
        "runtime": {"ticks_live": 3, "ticks_sandbox": 3, "default_quantity": 1.0},
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "priority", "tie_breaker": "priority"},
    }
    cfg = tmp_path / "plan.json"
    cfg.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rid = "rt_timeline"
    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    client = TestClient(app)
    r = client.get(f"/runs/{rid}/events?env=live&tail=100")
    assert r.status_code == 200
    payload = r.json()

    tl = payload.get("timeline")
    assert isinstance(tl, list)
    assert tl

    ts_prev = -1
    for ev in tl:
        assert isinstance(ev, dict)
        ts = ev.get("ts")
        assert isinstance(ts, int)
        assert ts >= ts_prev
        ts_prev = ts

        assert "reason_zh" in ev
        assert "side_zh" in ev
        assert "position_side_zh" in ev
