from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from math import sqrt
from typing import Any

from adapters.marketdata.base import MarketQuote
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


def positive_int(value: object, *, name: str, default: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return max(1, value)


def positive_float(value: object, *, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return max(0.0, float(value))


def direction_param(value: object) -> str:
    if value in {"long", "short", "both"}:
        return str(value)
    return "both"


def mean(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items)


def stdev(values: Iterable[float]) -> float:
    items = list(values)
    if len(items) < 2:
        return 0.0
    avg = mean(items)
    var = sum((v - avg) * (v - avg) for v in items) / len(items)
    return sqrt(var)


def signal(
    *,
    strategy_name: str,
    symbol: str,
    quote: MarketQuote,
    decision: Decision,
    reason: str,
    confidence: float,
    strength: SignalStrength,
    raw: dict[str, Any] | None = None,
) -> SignalDecision:
    if decision == Decision.OPEN_LONG:
        side = Side.BUY
        position_side = PositionSide.LONG
    elif decision in {Decision.OPEN_SHORT, Decision.CLOSE}:
        side = Side.SELL
        position_side = PositionSide.SHORT if decision == Decision.OPEN_SHORT else PositionSide.FLAT
    else:
        side = Side.NONE
        position_side = PositionSide.FLAT

    return SignalDecision(
        decision=decision,
        side=side,
        strength=strength,
        confidence=confidence,
        reason=reason,
        signal_id=f"{strategy_name}:{symbol}:{quote.ts}",
        strategy_name=strategy_name,
        symbol=symbol,
        instrument_id=symbol,
        trade_instrument_id=f"{symbol}_main",
        ts=quote.ts,
        bar_ts=quote.ts,
        bar_time=str(quote.ts),
        position_side=position_side,
        expected_price=quote.price,
        raw=raw,
    )


def hold(
    *,
    strategy_name: str,
    symbol: str,
    quote: MarketQuote,
    reason: str,
    raw: dict[str, Any] | None = None,
) -> SignalDecision:
    return signal(
        strategy_name=strategy_name,
        symbol=symbol,
        quote=quote,
        decision=Decision.HOLD,
        reason=reason,
        confidence=0.0,
        strength=SignalStrength.WEAK,
        raw=raw,
    )


@dataclass
class RollingSeries:
    maxlen: int
    prices: deque[float] = field(default_factory=deque)
    volumes: deque[float] = field(default_factory=deque)

    def append(self, quote: MarketQuote) -> None:
        if len(self.prices) >= self.maxlen:
            self.prices.popleft()
        if len(self.volumes) >= self.maxlen:
            self.volumes.popleft()
        self.prices.append(float(quote.price))
        if quote.volume is not None:
            self.volumes.append(float(quote.volume))
