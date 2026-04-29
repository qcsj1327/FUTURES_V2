from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.feature import FeatureSnapshot


@dataclass(frozen=True)
class MarketContext:
    symbol: str
    instrument_id: str
    trade_instrument_id: str
    ts: int
    bar_ts: int
    bar_time: str
    timeframe: str
    trading_date: str
    market_phase: str
    market_mode: str
    is_trading_time: bool
    last_price: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    feature_snapshot: FeatureSnapshot | None = None
    raw: dict[str, Any] | None = None
