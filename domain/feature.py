from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureSnapshot:
    ts: int
    bar_ts: int
    bar_time: str
    timeframe: str
    returns: float | None = None
    bar_return: float | None = None
    range: float | None = None
    price_range: float | None = None
    atr: float | None = None
    volume_ratio: float | None = None
    breakout_level: float | None = None
    moving_average: float | None = None
    bias: float | None = None
