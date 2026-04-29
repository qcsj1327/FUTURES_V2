from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.enums import OrderStatus, PositionSide, Side


@dataclass(frozen=True)
class OrderEvent:
    strategy_name: str
    instrument_id: str
    trade_instrument_id: str
    order_id: str
    side: Side
    position_side: PositionSide
    quantity: float
    status: OrderStatus
    ts: int
    reason: str | None = None
    client_order_id: str | None = None
    runtime_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FillEvent:
    strategy_name: str
    instrument_id: str
    trade_instrument_id: str
    order_id: str
    side: Side
    position_side: PositionSide
    quantity: float
    fill_price: float
    ts: int
    fill_id: str | None = None
    client_order_id: str | None = None
    runtime_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
