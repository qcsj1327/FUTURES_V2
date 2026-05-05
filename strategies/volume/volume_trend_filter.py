from __future__ import annotations

from dataclasses import dataclass, field

from adapters.marketdata.base import MarketQuote
from domain.enums import Decision, SignalStrength
from domain.signal import SignalDecision
from strategies.base.strategy import Strategy
from strategies.volume._common import (
    RollingSeries,
    hold,
    mean,
    quote_for_timeframe,
    signal,
    strict_direction,
    strict_positive_float,
    strict_positive_int,
    strict_timeframe,
)


@dataclass
class VolumeTrendFilter(Strategy):
    momentum_window: int = 20
    vol_window: int = 50
    min_vol_mult: float = 1.0
    direction: str = "both"
    timeframe: str = "spot"
    _state: dict[str, RollingSeries] = field(default_factory=dict, init=False)

    @classmethod
    def from_params(cls, params: dict[str, object]) -> VolumeTrendFilter:
        return cls(
            momentum_window=strict_positive_int(params, "momentum_window"),
            vol_window=strict_positive_int(params, "vol_window"),
            min_vol_mult=strict_positive_float(params, "min_vol_mult"),
            direction=strict_direction(params, "direction"),
            timeframe=strict_timeframe(params),
        )

    def _series(self, symbol: str) -> RollingSeries:
        maxlen = max(self.momentum_window + 1, self.vol_window)
        if symbol not in self._state:
            self._state[symbol] = RollingSeries(maxlen=maxlen)
        return self._state[symbol]

    def generate(self, symbol: str, quote: MarketQuote) -> SignalDecision:
        try:
            quote = quote_for_timeframe(quote, self.timeframe)
        except KeyError:
            return hold(
                strategy_name="volume_trend_filter",
                symbol=symbol,
                quote=quote,
                reason="missing_timeframe_bar",
                raw={"timeframe": self.timeframe},
            )
        series = self._series(symbol)
        if quote.volume is None:
            series.append(quote)
            return hold(
                strategy_name="volume_trend_filter",
                symbol=symbol,
                quote=quote,
                reason="missing_volume",
            )

        ready = (
            len(series.prices) >= self.momentum_window + 1
            and len(series.volumes) >= self.vol_window
        )
        if not ready:
            series.append(quote)
            return hold(
                strategy_name="volume_trend_filter",
                symbol=symbol,
                quote=quote,
                reason="warming_up",
            )

        past_price = list(series.prices)[-self.momentum_window]
        vol_ma = mean(list(series.volumes)[-self.vol_window :])
        volume_ok = quote.volume >= vol_ma * self.min_vol_mult
        momentum = quote.price - past_price
        raw = {
            "past_price": past_price,
            "momentum": momentum,
            "vol_ma": vol_ma,
            "timeframe": self.timeframe,
        }
        series.append(quote)

        if not volume_ok or momentum == 0.0:
            return hold(
                strategy_name="volume_trend_filter",
                symbol=symbol,
                quote=quote,
                reason="volume_filter_blocked" if not volume_ok else "flat_momentum",
                raw=raw,
            )
        if momentum > 0.0 and self.direction in {"long", "both"}:
            return signal(
                strategy_name="volume_trend_filter",
                symbol=symbol,
                quote=quote,
                decision=Decision.OPEN_LONG,
                reason="volume_confirmed_uptrend",
                confidence=0.75,
                strength=SignalStrength.MEDIUM,
                raw=raw,
            )
        if momentum < 0.0 and self.direction in {"short", "both"}:
            return signal(
                strategy_name="volume_trend_filter",
                symbol=symbol,
                quote=quote,
                decision=Decision.OPEN_SHORT,
                reason="volume_confirmed_downtrend",
                confidence=0.75,
                strength=SignalStrength.MEDIUM,
                raw=raw,
            )
        return hold(
            strategy_name="volume_trend_filter",
            symbol=symbol,
            quote=quote,
            reason="direction_blocked",
            raw=raw,
        )
