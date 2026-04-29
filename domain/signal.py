from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.enums import Decision, PositionSide, Side, SignalStrength


@dataclass(frozen=True)
class SignalCandidate:
    signal_id: str
    strategy_name: str
    symbol: str
    instrument_id: str
    trade_instrument_id: str
    ts: int
    bar_ts: int
    bar_time: str
    decision: Decision
    side: Side
    position_side: PositionSide
    confidence: float
    strength: SignalStrength
    reason: str
    expected_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    holding_period_hint: int | None = None
    tags: list[str] = field(default_factory=list)
    features_ref: str | None = None
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class SignalDecision:
    decision: Decision
    side: Side
    strength: SignalStrength
    confidence: float
    reason: str
    signal_id: str | None = None
    strategy_name: str | None = None
    symbol: str | None = None
    instrument_id: str | None = None
    trade_instrument_id: str | None = None
    runtime_id: str | None = None
    ts: int | None = None
    bar_ts: int | None = None
    bar_time: str | None = None
    position_side: PositionSide | None = None
    expected_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    tags: list[str] = field(default_factory=list)
    raw: dict[str, Any] | None = None
