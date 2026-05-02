from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scripts.run_plan import main as run_plan_main
from web.server import app


def _write_plan(path: Path, *, min_events: int, router_mode: str, strategy_name: str) -> None:
    plan = {
        "schema_version": 1,
        "env": "dev",
        "universe": {"symbols": ["au"]},
        "strategies": [
            {
                "name": strategy_name,
                "params": {"force_decision": "HOLD"},
                "symbols": ["au"],
                "priority": 10,
                "weight": 1.0,
            }
        ],
        "runtime": {"ticks_live": 1, "ticks_sandbox": 1, "default_quantity": 1.0},
        "promotion": {
            "min_events": min_events,
            "min_success_rate_improvement": -1.0,
            "max_consecutive_failures": 99,
        },
        "router": {"mode": router_mode, "tie_breaker": "priority"},
    }
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")


def test_runs_filters_and_manifests_runtime_filter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    cfg_ok = tmp_path / "ok.json"
    cfg_bad = tmp_path / "bad.json"

    _write_plan(cfg_ok, min_events=1, router_mode="priority", strategy_name="simple_strategy")
    _write_plan(cfg_bad, min_events=999, router_mode="netting", strategy_name="simple_strategy_alt")

    assert run_plan_main(["--config", str(cfg_ok), "--runtime-id", "rt_ok", "--clean"]) == 0
    assert run_plan_main(["--config", str(cfg_bad), "--runtime-id", "rt_bad"]) == 0

    client = TestClient(app)

    r_all = client.get("/runs?limit=200")
    assert r_all.status_code == 200
    ids = [x["runtime_id"] for x in r_all.json()]
    assert "rt_ok" in ids and "rt_bad" in ids

    r_appr_true = client.get("/runs?approved=true")
    ids_true = [x["runtime_id"] for x in r_appr_true.json()]
    assert "rt_ok" in ids_true
    assert "rt_bad" not in ids_true

    r_appr_false = client.get("/runs?approved=false")
    ids_false = [x["runtime_id"] for x in r_appr_false.json()]
    assert "rt_bad" in ids_false
    assert "rt_ok" not in ids_false

    r_router = client.get("/runs?router_mode=netting")
    ids_rm = [x["runtime_id"] for x in r_router.json()]
    assert ids_rm == ["rt_bad"]

    r_strategy = client.get("/runs?strategy=simple_strategy")
    ids_s = [x["runtime_id"] for x in r_strategy.json()]
    assert ids_s == ["rt_ok"]

    m_ok = client.get("/manifests?runtime_id=rt_ok")
    assert m_ok.status_code == 200
    assert all(x.startswith("manifest_rt_ok_") for x in m_ok.json())

    m_bad = client.get("/manifests?runtime_id=rt_bad")
    assert m_bad.status_code == 200
    assert all(x.startswith("manifest_rt_bad_") for x in m_bad.json())


def test_runs_pagination_limit_offset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    cfg = tmp_path / "p.json"
    _write_plan(cfg, min_events=1, router_mode="priority", strategy_name="simple_strategy")

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_1", "--clean"]) == 0
    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_2"]) == 0
    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_3"]) == 0

    client = TestClient(app)

    r1 = client.get("/runs?limit=1&offset=0")
    assert r1.status_code == 200
    assert len(r1.json()) == 1

    r2 = client.get("/runs?limit=2&offset=1")
    assert r2.status_code == 200
    assert len(r2.json()) <= 2
