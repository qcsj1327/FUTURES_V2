from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scripts.run_plan import main as run_plan_main
from web.server import app


def test_web_dashboard_routes_load_core_events_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.topn_switch_calendar.json"
    rid = "rt_web_dashboard_contract"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    client = TestClient(app)
    assert client.get("/health").status_code == 200

    runs = client.get("/runs").json()
    assert any(item["runtime_id"] == rid for item in runs)

    detail = client.get(f"/runs/{rid}").json()
    assert detail["runtime_id"] == rid
    assert isinstance(detail.get("warnings"), list)

    dashboard = client.get(f"/runs/{rid}/dashboard").json()
    assert dashboard["runtime_id"] == rid
    assert "portfolio" in dashboard
    assert "lifecycle_stats" in dashboard
    assert "active_symbols" in dashboard
    assert dashboard["dashboard_projection"]["schema_version"] == 1
    assert "pending_orders" in dashboard["dashboard_projection"]
    assert "quotes" in dashboard["dashboard_projection"]

    for event_type in ("order_lifecycle", "rank", "strategy_score", "roll"):
        response = client.get(
            f"/runs/{rid}/events",
            params={"event_type": event_type, "tail": 200},
        )
        assert response.status_code == 200
        assert "timeline" in response.json()
