from __future__ import annotations

import json
from pathlib import Path

import pytest

from adapters.storage.datastore_fs import JSONLFileDataStore
from core.services.runtime.datastore import InvalidEventEnvelopeError
from core.services.runtime.event_codec import (
    build_base_event,
    encode_datastore_event,
    encode_fill_event,
    encode_order_event,
)
from domain.enums import OrderStatus, PositionSide, Side
from domain.event import FillEvent, OrderEvent

MIN_ENVELOPE_FIELDS = {
    "schema_version",
    "event_id",
    "event_type",
    "runtime_id",
    "runtime_profile",
    "datastore_scope",
    "execution_env",
    "broker_profile",
    "submit_mode",
    "is_live",
    "is_simulated_execution",
    "generated_at",
    "source",
    "payload_type",
}

ENVELOPE_ONLY_FIELDS = {
    "runtime_profile",
    "datastore_scope",
    "execution_env",
    "broker_profile",
    "submit_mode",
    "is_live",
    "is_simulated_execution",
    "source",
}


def _base(scope: str = "local") -> dict[str, object]:
    return build_base_event(
        ts=1,
        runtime_id="rt_envelope",
        scope=scope,
        strategy_name="strategy",
        symbol="au",
        strategy_impl="Strategy",
    )


def _store(tmp_path: Path, scope: str = "local") -> JSONLFileDataStore:
    return JSONLFileDataStore(root_dir=tmp_path / scope, scope=scope, runtime_id="rt_envelope")


def test_encoded_order_event_is_envelope_plus_payload(tmp_path: Path) -> None:
    order = OrderEvent(
        strategy_name="strategy",
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        order_id="order-1",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=1.0,
        status=OrderStatus.SUBMITTED,
        ts=1,
        runtime_id="rt_envelope",
        metadata={"runtime_profile": "bad", "source": "bad"},
    )
    event = encode_datastore_event(
        base=_base(),
        event_type="order",
        payload_type="order_event",
        source="runtime",
        payload=encode_order_event(order),
    )

    assert set(event) == {"envelope", "payload"}
    assert MIN_ENVELOPE_FIELDS <= set(event["envelope"])
    assert event["envelope"]["payload_type"] == "order_event"
    assert ENVELOPE_ONLY_FIELDS.isdisjoint(set(event["payload"]))

    store = _store(tmp_path)
    store.append_order_event(event, scope="local")
    raw = json.loads(
        (tmp_path / "local" / "rt_envelope" / "order_events.jsonl")
        .read_text(encoding="utf-8")
        .strip()
    )
    assert set(raw) == {"envelope", "payload"}


def test_encoded_fill_event_is_envelope_plus_payload(tmp_path: Path) -> None:
    fill = FillEvent(
        strategy_name="strategy",
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        order_id="order-1",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=1.0,
        fill_price=100.0,
        ts=1,
        runtime_id="rt_envelope",
    )
    event = encode_datastore_event(
        base=_base(),
        event_type="fill",
        payload_type="fill_event",
        source="runtime",
        payload=encode_fill_event(fill),
    )

    assert MIN_ENVELOPE_FIELDS <= set(event["envelope"])
    assert event["envelope"]["payload_type"] == "fill_event"
    assert ENVELOPE_ONLY_FIELDS.isdisjoint(set(event["payload"]))

    _store(tmp_path).append_fill_event(event, scope="local")


def test_missing_envelope_rejected_by_datastore(tmp_path: Path) -> None:
    with pytest.raises(InvalidEventEnvelopeError, match="missing envelope"):
        _store(tmp_path).append_order_event({"payload": {"order_id": "o1"}}, scope="local")


def test_scope_mismatch_rejected_by_datastore(tmp_path: Path) -> None:
    event = encode_datastore_event(
        base=_base("local"),
        event_type="order",
        payload_type="order_event",
        source="runtime",
        payload={"order_id": "o1"},
    )
    with pytest.raises(InvalidEventEnvelopeError, match="datastore_scope mismatch"):
        _store(tmp_path, "live").append_order_event(event, scope="live")


def test_local_and_dryrun_events_cannot_write_live_scope(tmp_path: Path) -> None:
    for source_scope in ("local", "dryrun"):
        event = encode_datastore_event(
            base=_base(source_scope),
            event_type="order",
            payload_type="order_event",
            source="runtime",
            payload={"order_id": source_scope},
        )
        with pytest.raises(InvalidEventEnvelopeError):
            _store(tmp_path, "live").append_order_event(event, scope="live")


def test_generated_at_event_id_payload_type_are_required(tmp_path: Path) -> None:
    event = encode_datastore_event(
        base=_base(),
        event_type="order",
        payload_type="order_event",
        source="runtime",
        payload={"order_id": "o1"},
    )
    for field in ("generated_at", "event_id", "payload_type"):
        broken = {"envelope": dict(event["envelope"]), "payload": dict(event["payload"])}
        broken["envelope"][field] = ""
        with pytest.raises(InvalidEventEnvelopeError, match=f"missing envelope.{field}"):
            _store(tmp_path).append_order_event(broken, scope="local")
