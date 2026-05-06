from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from math import sqrt
from typing import Any

from core.services.marketdata.types import MarketQuote
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision

ALLOWED_TIMEFRAMES = {"spot", "5m", "15m", "1h", "1d"}


def strict_positive_int(params: dict[str, object], name: str) -> int:
    value = params.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be positive int")
    if value < 1:
        raise ValueError(f"{name} must be positive int")
    return value


def strict_positive_float(params: dict[str, object], name: str) -> float:
    value = params.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be positive number")
    out = float(value)
    if out <= 0.0:
        raise ValueError(f"{name} must be positive number")
    return out


def strict_direction(params: dict[str, object], name: str) -> str:
    value = params.get(name)
    if value in {"long", "short", "both"}:
        return str(value)
    raise ValueError(f"{name} must be long|short|both")


def strict_timeframe(params: dict[str, object], name: str = "timeframe") -> str:
    value = params.get(name, "spot")
    if value in ALLOWED_TIMEFRAMES:
        return str(value)
    raise ValueError(f"{name} must be spot|5m|15m|1h|1d")


def quote_for_timeframe(quote: MarketQuote, timeframe: str) -> MarketQuote:
    if timeframe == "spot":
        return quote
    bar = quote.get_bar(timeframe)
    if bar is None:
        raise KeyError(timeframe)
    return MarketQuote(
        symbol=quote.symbol,
        price=bar.close,
        volume=bar.volume,
        ts=bar.ts,
        bars=quote.bars,
    )


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
        trade_instrument_id=None,
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
