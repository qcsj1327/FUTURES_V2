from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.enums import OrderStatus, PositionSide, Side


@dataclass
class OrderState:
    order_id: str
    instrument_id: str
    trade_instrument_id: str
    side: Side
    position_side: PositionSide
    quantity: float
    status: OrderStatus
    ts: int | None = None
    filled_quantity: float = 0.0
    avg_fill_price: float | None = None
    client_order_id: str | None = None
    runtime_id: str | None = None
    strategy_name: str | None = None
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PositionState:
    instrument_id: str
    trade_instrument_id: str
    position_side: PositionSide = PositionSide.FLAT
    quantity: float = 0.0
    avg_price: float | None = None
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    runtime_id: str | None = None
    strategy_name: str | None = None
    updated_ts: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyState:
    strategy_name: str
    runtime_id: str | None = None
    enabled: bool = True
    last_signal_id: str | None = None
    last_bar_ts: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemState:
    runtime_id: str
    is_running: bool = False
    is_paused: bool = False
    updated_ts: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PnLSnapshot:
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    commission: float = 0.0


@dataclass
class StateSnapshot:
    runtime_id: str
    orders: list[OrderState] = field(default_factory=list)
    positions: list[PositionState] = field(default_factory=list)
    strategies: list[StrategyState] = field(default_factory=list)
    system: SystemState | None = None
    pnl: PnLSnapshot = field(default_factory=PnLSnapshot)
