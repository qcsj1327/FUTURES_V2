from __future__ import annotations

import json
from pathlib import Path

from core.services.runtime.event_codec import encode_datastore_event
from web.api.events import get_run_events


def _append(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload) + "\n")


def _event(scope: str, order_id: str) -> dict[str, object]:
    return encode_datastore_event(
        base={
            "ts": 1,
            "runtime_id": "rt_events",
            "scope": scope,
            "symbol": "au",
            "strategy_name": "contract",
            "strategy_impl": "contract",
        },
        event_type="order_lifecycle",
        payload_type="order_lifecycle",
        source="contract",
        payload={"order_id": order_id, "status": "SUBMITTED", "quantity": 1.0, "ts": 1},
    )


def test_events_api_does_not_return_legacy_flat_row(tmp_path: Path) -> None:
    path = tmp_path / "store" / "live" / "rt_events" / "order_lifecycle_events.jsonl"
    _append(path, {"order_id": "legacy", "status": "SUBMITTED"})

    payload = get_run_events(runtime_id="rt_events", scope="live", store_root=tmp_path / "store")

    assert payload["order_lifecycle_events"] == []
    assert payload["invalid_count"] == 1
    assert payload["invalid_reasons"]["missing_envelope"] == 1


def test_events_api_does_not_return_scope_mismatch_row(tmp_path: Path) -> None:
    path = tmp_path / "store" / "live" / "rt_events" / "order_lifecycle_events.jsonl"
    _append(path, _event("dryrun", "dryrun-order"))

    payload = get_run_events(runtime_id="rt_events", scope="live", store_root=tmp_path / "store")

    assert payload["order_lifecycle_events"] == []
    assert payload["invalid_count"] == 1
    assert "runtime_profile_mismatch:dryrun:live" in payload["invalid_reasons"]


def test_events_api_returns_envelope_scope_source_fields(tmp_path: Path) -> None:
    path = tmp_path / "store" / "live" / "rt_events" / "order_lifecycle_events.jsonl"
    _append(path, _event("live", "live-order"))

    payload = get_run_events(runtime_id="rt_events", scope="live", store_root=tmp_path / "store")

    row = payload["order_lifecycle_events"][0]
    assert row["runtime_profile"] == "live"
    assert row["datastore_scope"] == "live"
    assert row["event_id"]
    assert row["source"] == "contract"
    assert row["payload_type"] == "order_lifecycle"
    assert payload["invalid_count"] == 0


def test_missing_envelope_counts_invalid_not_events(tmp_path: Path) -> None:
    path = tmp_path / "store" / "live" / "rt_events" / "order_events.jsonl"
    _append(path, {"order_id": "missing-envelope"})
    _append(path, _event("live", "valid"))

    payload = get_run_events(runtime_id="rt_events", scope="live", store_root=tmp_path / "store")

    assert [row["order_id"] for row in payload["order_events"]] == ["valid"]
    assert payload["invalid_count"] == 1
