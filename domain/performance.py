from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.enums import PositionSide, Side


@dataclass(frozen=True)
class ClosedTrade:
    trade_id: str
    strategy_name: str
    symbol: str
    instrument_id: str
    trade_instrument_id: str
    side: Side
    position_side: PositionSide
    quantity: float
    entry_price: float
    exit_price: float
    entry_ts: int
    exit_ts: int
    realized_pnl: float
    commission: float = 0.0
    reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PerformanceSnapshot:
    ts: int
    trading_day: str
    strategy_name: str
    symbol: str
    instrument_id: str
    trade_instrument_id: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float | None = None
    profit_factor: float | None = None
    avg_win: float | None = None
    avg_loss: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
