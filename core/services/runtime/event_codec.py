from __future__ import annotations

import uuid
from dataclasses import is_dataclass
from datetime import UTC, datetime
from typing import Any

from domain.event import FillEvent, OrderEvent

CANONICAL_SCOPES = {"local", "dryrun", "live"}
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


def build_base_event(
    *,
    ts: int,
    runtime_id: str,
    scope: str,
    strategy_name: str,
    symbol: str,
    strategy_impl: str | None = None,
) -> dict[str, Any]:
    # strategy_name is kept for compatibility; strategy_id is the stable config id.
    strategy_id = strategy_name
    return {
        "ts": ts,
        "runtime_id": runtime_id,
        "scope": scope,
        "symbol": symbol,
        "strategy_name": strategy_name,  # legacy, stable = strategy_id
        "strategy_id": strategy_id,      # new
        "strategy_impl": (strategy_impl or "unknown"),  # new (debug)
    }


def build_event_envelope(
    *,
    event_type: str,
    runtime_id: str,
    runtime_profile: str,
    datastore_scope: str,
    payload_type: str,
    source: str,
    execution_env: str | None = None,
    broker_profile: str | None = None,
    submit_mode: str | None = None,
) -> dict[str, Any]:
    if runtime_profile not in CANONICAL_SCOPES:
        raise ValueError(f"invalid_runtime_profile:{runtime_profile}")
    if datastore_scope not in CANONICAL_SCOPES:
        raise ValueError(f"invalid_datastore_scope:{datastore_scope}")
    if runtime_profile != datastore_scope:
        raise ValueError(
            f"runtime_profile_datastore_scope_mismatch:{runtime_profile}:{datastore_scope}"
        )
    return {
        "schema_version": "1",
        "event_id": uuid.uuid4().hex,
        "event_type": event_type,
        "runtime_id": runtime_id,
        "runtime_profile": runtime_profile,
        "datastore_scope": datastore_scope,
        "execution_env": execution_env or _default_execution_env(runtime_profile),
        "broker_profile": broker_profile or _default_broker_profile(runtime_profile),
        "submit_mode": submit_mode or _default_submit_mode(runtime_profile),
        "is_live": runtime_profile == "live",
        "is_simulated_execution": runtime_profile == "local",
        "generated_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "source": source,
        "payload_type": payload_type,
    }


def encode_datastore_event(
    *,
    base: dict[str, Any],
    event_type: str,
    payload_type: str,
    payload: dict[str, Any],
    source: str = "runtime",
) -> dict[str, Any]:
    scope = str(base.get("scope") or base.get("datastore_scope") or "")
    runtime_id = str(base.get("runtime_id") or "")
    envelope = build_event_envelope(
        event_type=event_type,
        runtime_id=runtime_id,
        runtime_profile=scope,
        datastore_scope=scope,
        payload_type=payload_type,
        source=source,
    )
    clean_base = _payload_without_envelope_fields(base)
    clean_base.pop("scope", None)
    clean_payload = _payload_without_envelope_fields(payload)
    return {
        "envelope": envelope,
        "payload": {
            **clean_base,
            **clean_payload,
        },
    }


def encode_order_event(order: object | None) -> dict[str, Any]:
    if isinstance(order, OrderEvent):
        payload = {
            "instrument_id": order.instrument_id,
            "trade_instrument_id": order.trade_instrument_id,
            "order_id": order.order_id,
            "side": order.side.value,
            "position_side": order.position_side.value,
            "quantity": order.quantity,
            "status": order.status.value,
            "reason": order.reason,
            "client_order_id": order.client_order_id,
            "event_runtime_id": order.runtime_id,
            **order.metadata,
        }
        return _payload_without_envelope_fields(payload)

    if order is None:
        return {}

    if is_dataclass(order):
        d = order.__dict__
        return {
            "instrument_id": d.get("instrument_id"),
            "trade_instrument_id": d.get("trade_instrument_id"),
            "side": getattr(d.get("side"), "value", d.get("side")),
            "position_side": getattr(d.get("position_side"), "value", d.get("position_side")),
            "quantity": d.get("quantity"),
            "price": d.get("price"),
            "stop_loss": d.get("stop_loss"),
            "take_profit": d.get("take_profit"),
        }

    return {
        "instrument_id": getattr(order, "instrument_id", None),
        "trade_instrument_id": getattr(order, "trade_instrument_id", None),
        "side": getattr(getattr(order, "side", None), "value", getattr(order, "side", None)),
        "position_side": getattr(
            getattr(order, "position_side", None),
            "value",
            getattr(order, "position_side", None),
        ),
        "quantity": getattr(order, "quantity", None),
        "price": getattr(order, "price", None),
        "stop_loss": getattr(order, "stop_loss", None),
        "take_profit": getattr(order, "take_profit", None),
    }


def encode_fill_event(event: FillEvent) -> dict[str, Any]:
    payload = {
        "instrument_id": event.instrument_id,
        "trade_instrument_id": event.trade_instrument_id,
        "order_id": event.order_id,
        "side": event.side.value,
        "position_side": event.position_side.value,
        "quantity": event.quantity,
        "fill_price": event.fill_price,
        "fill_id": event.fill_id,
        "client_order_id": event.client_order_id,
        "event_runtime_id": event.runtime_id,
        **event.metadata,
    }
    return _payload_without_envelope_fields(payload)


def _payload_without_envelope_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in payload.items() if k not in ENVELOPE_ONLY_FIELDS}


def _default_execution_env(scope: str) -> str:
    if scope == "local":
        return "simulated"
    return scope


def _default_broker_profile(scope: str) -> str:
    if scope == "local":
        return "simulated"
    return "tqkq"


def _default_submit_mode(scope: str) -> str:
    if scope == "local":
        return "none"
    return scope
