from __future__ import annotations

from pathlib import Path

import pytest

from adapters.storage.datastore_fs import JSONLFileDataStore
from adapters.storage.datastore_memory import MemoryDataStore
from core.services.runtime.datastore import InvalidEventEnvelopeError, ScopeMismatchError
from core.services.runtime.event_codec import encode_datastore_event


def _order_event(runtime_id: str, scope: str, order_id: str) -> dict[str, object]:
    return encode_datastore_event(
        base={
            "ts": 1,
            "runtime_id": runtime_id,
            "scope": scope,
            "symbol": "au",
            "strategy_name": "test",
            "strategy_id": "test",
            "strategy_impl": "test",
        },
        event_type="order",
        payload_type="order_event",
        source="test",
        payload={"order_id": order_id, "instrument_id": "au"},
    )


def test_memory_store_scope_mismatch_raises() -> None:
    s = MemoryDataStore(scope="live", runtime_id="r1")
    with pytest.raises(ScopeMismatchError):
        s.append_order_event({"x": 1}, scope="dryrun")


def test_memory_store_rejects_missing_event_envelope() -> None:
    s = MemoryDataStore(scope="live", runtime_id="r1")
    with pytest.raises(InvalidEventEnvelopeError, match="missing envelope"):
        s.append_order_event({"x": 1}, scope="live")


def test_fs_store_writes_are_isolated_by_scope(tmp_path: Path) -> None:
    live = JSONLFileDataStore(root_dir=tmp_path / "live", scope="live", runtime_id="r1")
    dryrun = JSONLFileDataStore(root_dir=tmp_path / "dryrun", scope="dryrun", runtime_id="r1")

    live.append_order_event(_order_event("r1", "live", "o1"), scope="live")
    dryrun.append_order_event(_order_event("r1", "dryrun", "o2"), scope="dryrun")

    live_path = tmp_path / "live" / "r1" / "order_events.jsonl"
    dryrun_path = tmp_path / "dryrun" / "r1" / "order_events.jsonl"

    assert live_path.exists()
    assert dryrun_path.exists()

    assert "o1" in live_path.read_text(encoding="utf-8")
    assert "o2" not in live_path.read_text(encoding="utf-8")

    assert "o2" in dryrun_path.read_text(encoding="utf-8")
    assert "o1" not in dryrun_path.read_text(encoding="utf-8")
