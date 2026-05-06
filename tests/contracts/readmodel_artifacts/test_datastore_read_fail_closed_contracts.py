from __future__ import annotations

import json
import pickle
from pathlib import Path

from adapters.storage.datastore_fs import JSONLFileDataStore
from core.services.runtime.event_codec import encode_datastore_event


def _store(tmp_path: Path, scope: str = "live") -> JSONLFileDataStore:
    return JSONLFileDataStore(
        root_dir=tmp_path / scope,
        scope=scope,
        runtime_id="rt_read_fail_closed",
    )


def _event(
    *,
    scope: str = "live",
    payload_type: str = "order_event",
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    return encode_datastore_event(
        base={
            "ts": 1,
            "runtime_id": "rt_read_fail_closed",
            "scope": scope,
            "symbol": "au",
            "strategy_name": "strategy",
            "strategy_id": "strategy",
            "strategy_impl": "Strategy",
        },
        event_type=payload_type,
        payload_type=payload_type,
        source="contract",
        payload=payload or {"order_id": "order-1"},
    )


def _write_jsonl(store: JSONLFileDataStore, filename: str, rows: list[object]) -> None:
    path = store.root_dir / store.runtime_id / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def test_read_order_events_does_not_return_legacy_flat_row(tmp_path: Path) -> None:
    store = _store(tmp_path, "live")
    _write_jsonl(
        store,
        "order_events.jsonl",
        [{"order_id": "legacy-flat", "runtime_profile": "live", "datastore_scope": "live"}],
    )

    assert store.read_order_events(scope="live") == []


def test_read_order_events_does_not_return_missing_envelope_row(tmp_path: Path) -> None:
    store = _store(tmp_path, "live")
    _write_jsonl(store, "order_events.jsonl", [{"payload": {"order_id": "missing-envelope"}}])

    assert store.read_order_events(scope="live") == []


def test_read_order_events_does_not_return_missing_payload_row(tmp_path: Path) -> None:
    store = _store(tmp_path, "live")
    event = _event(scope="live")
    event.pop("payload")
    _write_jsonl(store, "order_events.jsonl", [event])

    assert store.read_order_events(scope="live") == []


def test_read_order_events_does_not_return_scope_mismatch_row(tmp_path: Path) -> None:
    store = _store(tmp_path, "live")
    _write_jsonl(store, "order_events.jsonl", [_event(scope="dryrun")])

    assert store.read_order_events(scope="live") == []


def test_read_order_events_does_not_return_payload_with_envelope_only_field(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path, "live")
    event = _event(scope="live", payload={"order_id": "bad-payload"})
    assert isinstance(event["payload"], dict)
    event["payload"]["datastore_scope"] = "live"
    _write_jsonl(
        store,
        "order_events.jsonl",
        [event],
    )

    assert store.read_order_events(scope="live") == []


def test_read_order_events_returns_only_current_enveloped_rows(tmp_path: Path) -> None:
    store = _store(tmp_path, "live")
    valid = _event(scope="live", payload={"order_id": "current"})
    _write_jsonl(
        store,
        "order_events.jsonl",
        [
            {"order_id": "legacy-flat"},
            _event(scope="dryrun", payload={"order_id": "wrong-scope"}),
            valid,
        ],
    )

    rows = store.read_order_events(scope="live")

    assert [row["order_id"] for row in rows] == ["current"]
    assert rows[0]["runtime_profile"] == "live"
    assert rows[0]["datastore_scope"] == "live"
    assert rows[0]["payload_type"] == "order_event"


def test_read_events_rejects_payload_type_mismatch(tmp_path: Path) -> None:
    store = _store(tmp_path, "live")
    _write_jsonl(store, "order_events.jsonl", [_event(scope="live", payload_type="fill_event")])

    assert store.read_order_events(scope="live") == []


def test_load_latest_snapshot_does_not_use_legacy_flat_fallback(tmp_path: Path) -> None:
    store = _store(tmp_path, "live")
    _write_jsonl(
        store,
        "portfolio_snapshots.jsonl",
        [{"ts": 1, "portfolio_file": "snapshots/portfolio_1.pkl"}],
    )

    assert store.load_latest_portfolio_snapshot(scope="live") is None


def test_load_latest_snapshot_does_not_use_scope_mismatch_row(tmp_path: Path) -> None:
    store = _store(tmp_path, "live")
    _write_jsonl(
        store,
        "portfolio_snapshots.jsonl",
        [
            _event(
                scope="dryrun",
                payload_type="snapshot",
                payload={"ts": 1, "portfolio_file": "snapshots/portfolio_1.pkl"},
            )
        ],
    )

    assert store.load_latest_portfolio_snapshot(scope="live") is None


def test_load_latest_snapshot_accepts_only_enveloped_snapshot_payload(tmp_path: Path) -> None:
    store = _store(tmp_path, "live")
    snapshot_dir = store.root_dir / store.runtime_id / "snapshots"
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    with (snapshot_dir / "portfolio_1.pkl").open("wb") as f:
        pickle.dump({"positions": {"au": 1}}, f)
    _write_jsonl(
        store,
        "portfolio_snapshots.jsonl",
        [
            _event(
                scope="live",
                payload_type="snapshot",
                payload={"ts": 1, "portfolio_file": "snapshots/portfolio_1.pkl"},
            )
        ],
    )

    assert store.load_latest_portfolio_snapshot(scope="live") == {"positions": {"au": 1}}
