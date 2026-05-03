from __future__ import annotations

from dataclasses import is_dataclass
from typing import Any


def build_base_event(
    *,
    ts: int,
    runtime_id: str,
    env: str,
    strategy_name: str,
    symbol: str,
    strategy_impl: str | None = None,
) -> dict[str, Any]:
    # strategy_name is kept for compatibility; strategy_id is the stable config id.
    strategy_id = strategy_name
    return {
        "ts": ts,
        "runtime_id": runtime_id,
        "env": env,
        "symbol": symbol,
        "strategy_name": strategy_name,  # legacy, stable = strategy_id
        "strategy_id": strategy_id,      # new
        "strategy_impl": (strategy_impl or "unknown"),  # new (debug)
    }


def encode_order_event(order: object | None) -> dict[str, Any]:
    if order is None:
        return {}

    if is_dataclass(order):
        d = order.__dict__
        return {
            "event_type": "order",
            "instrument_id": d.get("instrument_id"),
            "trade_instrument_id": d.get("trade_instrument_id"),
            "side": getattr(d.get("side"), "value", d.get("side")),
            "position_side": getattr(d.get("position_side"), "value", d.get("position_side")),
            "quantity": d.get("quantity"),
            "price": d.get("price"),
        }

    return {
        "event_type": "order",
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
    }


def encode_execution_event(exec_result: object) -> dict[str, Any]:
    if is_dataclass(exec_result):
        d = exec_result.__dict__
        return {
            "event_type": "execution",
            "success": d.get("success"),
            "reason": d.get("reason"),
            "filled_quantity": d.get("filled_quantity"),
            "remaining_quantity": d.get("remaining_quantity"),
            "avg_fill_price": d.get("avg_fill_price"),
            "order_id": d.get("order_id"),
        }

    return {
        "event_type": "execution",
        "success": getattr(exec_result, "success", None),
        "reason": getattr(exec_result, "reason", None),
        "filled_quantity": getattr(exec_result, "filled_quantity", None),
        "remaining_quantity": getattr(exec_result, "remaining_quantity", None),
        "avg_fill_price": getattr(exec_result, "avg_fill_price", None),
        "order_id": getattr(exec_result, "order_id", None),
    }
