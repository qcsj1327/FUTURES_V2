from __future__ import annotations

from dataclasses import dataclass

from domain.enums import ExecutionStatus, PositionSide, Side


@dataclass(frozen=True)
class ExecutionOrder:
    instrument_id: str
    side: Side
    position_side: PositionSide
    quantity: float
    order_type: str
    trade_instrument_id: str | None = None
    price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    client_order_id: str | None = None


@dataclass(frozen=True)
class ExecutionResult:
    success: bool
    status: ExecutionStatus
    order_id: str | None = None
    ts: int | None = None
    fill_price: float | None = None
    reason: str | None = None
