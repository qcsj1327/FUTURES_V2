from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _to_primitive(x: Any) -> Any:
    # Make enums/objects serializable without relying on str() for the whole payload.
    if x is None:
        return None
    if isinstance(x, (bool, int, float, str)):
        return x
    # common enum pattern
    name = getattr(x, "name", None)
    if isinstance(name, str):
        return name
    value = getattr(x, "value", None)
    if isinstance(value, (bool, int, float, str)):
        return value
    return str(x)


def encode_order_event(order: Any) -> dict[str, Any]:
    """
    Minimal stable order schema for replay/learning.
    We do NOT depend on domain types here (adapter-agnostic).
    """
    if order is None:
        return {}

    # best-effort field extraction (works across domain order variants)
    d: dict[str, Any] = {"event_type": "order"}
    for k in (
        "order_id",
        "symbol",
        "action",
        "side",
        "position_side",
        "quantity",
        "price",
        "type",
        "reduce_only",
    ):
        if hasattr(order, k):
            d[k] = _to_primitive(getattr(order, k))
    # some orders store identifiers under other names
    for alt, key in (("id", "order_id"), ("qty", "quantity")):
        if key not in d and hasattr(order, alt):
            d[key] = _to_primitive(getattr(order, alt))
    return d


def encode_execution_event(exec_result: Any) -> dict[str, Any]:
    """
    Minimal stable execution result schema.
    Always emits success + reason when present.
    """
    d: dict[str, Any] = {"event_type": "execution"}
    for k in (
        "success",
        "reason",
        "rejected_reason",
        "filled_quantity",
        "remaining_quantity",
        "avg_fill_price",
        "commission",
        "slippage",
        "order_id",
    ):
        if hasattr(exec_result, k):
            d[k] = _to_primitive(getattr(exec_result, k))

    # success is the only hard requirement (default False if missing)
    if "success" not in d:
        d["success"] = False

    return d


def build_base_event(
    *,
    ts: int,
    runtime_id: str,
    env: str,
    strategy_name: str,
    symbol: str | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ts": ts,
        "runtime_id": runtime_id,
        "env": env,
        "strategy_name": strategy_name,
    }
    if symbol is not None:
        base["symbol"] = symbol
    if extra:
        base.update({k: _to_primitive(v) for k, v in extra.items()})
    return base
