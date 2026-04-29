from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from domain.enums import Decision, PositionSide, Side, SignalStrength, TriggerLifecycle


@dataclass(frozen=True)
class TriggerResult:
    decision: Decision
    side: Side
    lifecycle: TriggerLifecycle
    triggered: bool
    runtime_id: str
    bar_ts: int | None = None
    signal_id: str | None = None
    strategy_name: str | None = None
    symbol: str | None = None
    instrument_id: str | None = None
    trade_instrument_id: str | None = None
    ts: int | None = None
    bar_time: str | None = None
    position_side: PositionSide | None = None
    confidence: float | None = None
    strength: SignalStrength | None = None
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
