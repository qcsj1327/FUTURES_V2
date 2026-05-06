from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from adapters.storage.datastore_fs import JSONLFileDataStore
from core.services.runtime.datastore import InvalidEventEnvelopeError
from core.services.runtime.event_codec import encode_datastore_event


def _event(scope: str) -> dict[str, Any]:
    return encode_datastore_event(
        base={
            "ts": 1,
            "runtime_id": "rt_scope_validation",
            "scope": scope,
            "symbol": "au",
            "strategy_name": "test",
            "strategy_id": "test",
            "strategy_impl": "test",
        },
        event_type="order",
        payload_type="order_event",
        source="test",
        payload={"order_id": "o1", "instrument_id": "au"},
    )


def _store(tmp_path: Path, scope: str) -> JSONLFileDataStore:
    return JSONLFileDataStore(
        root_dir=tmp_path / scope,
        scope=scope,
        runtime_id="rt_scope_validation",
    )


def test_datastore_append_validates_envelope_datastore_scope(tmp_path: Path) -> None:
    event = _event("local")

    with pytest.raises(InvalidEventEnvelopeError, match="datastore_scope mismatch"):
        _store(tmp_path, "live").append_order_event(event, scope="live")


def test_datastore_append_validates_runtime_profile(tmp_path: Path) -> None:
    event = _event("local")
    event["envelope"]["runtime_profile"] = "invalid_profile"

    with pytest.raises(InvalidEventEnvelopeError, match="invalid runtime_profile"):
        _store(tmp_path, "local").append_order_event(event, scope="local")


def test_datastore_append_validates_is_live_matches_scope(tmp_path: Path) -> None:
    event = _event("dryrun")
    event["envelope"]["is_live"] = True

    with pytest.raises(InvalidEventEnvelopeError, match="is_live mismatch"):
        _store(tmp_path, "dryrun").append_order_event(event, scope="dryrun")


def test_datastore_does_not_auto_correct_wrong_scope(tmp_path: Path) -> None:
    event = _event("local")

    with pytest.raises(InvalidEventEnvelopeError):
        _store(tmp_path, "live").append_order_event(event, scope="live")

    assert not (tmp_path / "live" / "rt_scope_validation" / "order_events.jsonl").exists()
    assert event["envelope"]["datastore_scope"] == "local"


def test_error_message_names_wrong_scope(tmp_path: Path) -> None:
    event = _event("dryrun")

    with pytest.raises(InvalidEventEnvelopeError, match="envelope=dryrun append=live"):
        _store(tmp_path, "live").append_order_event(event, scope="live")
