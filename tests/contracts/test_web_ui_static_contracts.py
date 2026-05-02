from __future__ import annotations

from fastapi.testclient import TestClient

from web.server import app


def test_ui_static_routes_exist() -> None:
    c = TestClient(app)

    r = c.get("/")
    assert r.status_code in (200, 307, 308)

    r2 = c.get("/ui")
    assert r2.status_code == 200
    assert "FUTURES_V2" in r2.text
