from __future__ import annotations

from dataclasses import dataclass

from domain.enums import ExecutionStatus, PositionSide, Side


@dataclass(frozen=True)
class FillApplication:
    order_id: str
    instrument_id: str
    trade_instrument_id: str
    side: Side
    position_side: PositionSide
    order_quantity: float
    filled_quantity: float
    fill_price: float
    status: ExecutionStatus
    ts: int | None
    client_order_id: str | None = None
    reason: str | None = None
    remaining_quantity: float | None = None
    avg_fill_price: float | None = None
