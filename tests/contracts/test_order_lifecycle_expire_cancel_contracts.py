from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main
from web.api.events import get_run_events


def _events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_order_lifecycle_v2_expire_cancel_on_ttl(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.order_lifecycle_v2.json"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_expire", "--clean"]) == 0

    path = tmp_path / "data" / "store" / "live" / "rt_expire" / "order_lifecycle_events.jsonl"
    events = _events(path)
    assert events
    assert any(e["status"] == "PARTIAL" for e in events)
    expired = [e for e in events if e["status"] == "EXPIRED"]
    assert expired
    assert {str(e["reason"]) for e in expired} == {"expired"}
    for event in expired:
        assert event["order_id"]
        assert event["trade_instrument_id"]
        assert event["remaining_quantity"] is not None

    api_payload = get_run_events(
        runtime_id="rt_expire",
        env="live",
        store_root=tmp_path / "data" / "store",
        event_type="order_lifecycle",
    )
    assert api_payload["timeline"]
    assert all(e["event_type"] == "order_lifecycle" for e in api_payload["timeline"])
