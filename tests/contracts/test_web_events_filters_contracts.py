from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scripts.run_plan import main as run_plan_main
from web.server import app


def test_events_filters_and_pagination(
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
        "runtime": {"ticks_live": 5, "ticks_sandbox": 5, "default_quantity": 1.0},
        "promotion": {
            "min_events": 1,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": "priority", "tie_breaker": "priority"},
    }
    cfg = tmp_path / "plan.json"
    cfg.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    rid = "rt_evt_filters"
    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    client = TestClient(app)

    r_all = client.get(f"/runs/{rid}/events?env=live&tail=500")
    assert r_all.status_code == 200
    payload = r_all.json()
    tl = payload.get("timeline")
    assert isinstance(tl, list) and tl

    # event_type filter: execution
    r_exec = client.get(f"/runs/{rid}/events?env=live&tail=500&event_type=execution")
    assert r_exec.status_code == 200
    tl_exec = r_exec.json()["timeline"]
    assert all(isinstance(x, dict) and x.get("event_type") == "execution" for x in tl_exec)

    # event_type filter: order
    r_ord = client.get(f"/runs/{rid}/events?env=live&tail=500&event_type=order")
    assert r_ord.status_code == 200
    tl_ord = r_ord.json()["timeline"]
    assert all(isinstance(x, dict) and x.get("event_type") == "order" for x in tl_ord)

    # since_ts: pick a mid ts
    mid_ts = tl[len(tl) // 2]["ts"]
    r_since = client.get(f"/runs/{rid}/events?env=live&tail=500&since_ts={mid_ts}")
    tl_since = r_since.json()["timeline"]
    assert all(isinstance(x, dict) and x.get("ts") >= mid_ts for x in tl_since)

    # pagination
    r_page = client.get(f"/runs/{rid}/events?env=live&tail=500&limit=2&offset=1")
    page = r_page.json()["timeline"]
    assert isinstance(page, list)
    assert len(page) <= 2
