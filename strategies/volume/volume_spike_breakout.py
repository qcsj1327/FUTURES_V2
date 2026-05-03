from __future__ import annotations

from dataclasses import dataclass, field

from adapters.marketdata.base import MarketQuote
from domain.enums import Decision, SignalStrength
from domain.signal import SignalDecision
from strategies.base.strategy import Strategy
from strategies.volume._common import (
    RollingSeries,
    direction_param,
    hold,
    mean,
    positive_float,
    positive_int,
    signal,
)


@dataclass
class VolumeSpikeBreakout(Strategy):
    window: int = 50
    spike_mult: float = 2.0
    breakout_lookback: int = 20
    direction: str = "both"
    _state: dict[str, RollingSeries] = field(default_factory=dict, init=False)

    @classmethod
    def from_params(cls, params: dict[str, object]) -> VolumeSpikeBreakout:
        return cls(
            window=positive_int(params.get("window"), name="window", default=50),
            spike_mult=positive_float(params.get("spike_mult"), default=2.0),
            breakout_lookback=positive_int(
                params.get("breakout_lookback"),
                name="breakout_lookback",
                default=20,
            ),
            direction=direction_param(params.get("direction")),
        )

    def _series(self, symbol: str) -> RollingSeries:
        maxlen = max(self.window, self.breakout_lookback)
        if symbol not in self._state:
            self._state[symbol] = RollingSeries(maxlen=maxlen)
        return self._state[symbol]

    def generate(self, symbol: str, quote: MarketQuote) -> SignalDecision:
        series = self._series(symbol)
        if quote.volume is None:
            series.append(quote)
            return hold(
                strategy_name="volume_spike_breakout",
                symbol=symbol,
                quote=quote,
                reason="missing_volume",
            )

        has_history = (
            len(series.volumes) >= self.window
            and len(series.prices) >= self.breakout_lookback
        )
        if not has_history:
            series.append(quote)
            return hold(
                strategy_name="volume_spike_breakout",
                symbol=symbol,
                quote=quote,
                reason="warming_up",
            )

        vol_ma = mean(list(series.volumes)[-self.window :])
        recent_prices = list(series.prices)[-self.breakout_lookback :]
        high = max(recent_prices)
        low = min(recent_prices)
        is_spike = quote.volume > vol_ma * self.spike_mult
        raw = {
            "price": quote.price,
            "volume": quote.volume,
            "vol_ma": vol_ma,
            "rolling_high": high,
            "rolling_low": low,
        }
        series.append(quote)

        if is_spike and quote.price > high and self.direction in {"long", "both"}:
            return signal(
                strategy_name="volume_spike_breakout",
                symbol=symbol,
                quote=quote,
                decision=Decision.OPEN_LONG,
                reason="volume_spike_high_breakout",
                confidence=1.0,
                strength=SignalStrength.STRONG,
                raw=raw,
            )
        if is_spike and quote.price < low and self.direction in {"short", "both"}:
            return signal(
                strategy_name="volume_spike_breakout",
                symbol=symbol,
                quote=quote,
                decision=Decision.OPEN_SHORT,
                reason="volume_spike_low_breakout",
                confidence=1.0,
                strength=SignalStrength.STRONG,
                raw=raw,
            )
        return hold(
            strategy_name="volume_spike_breakout",
            symbol=symbol,
            quote=quote,
            reason="no_breakout",
            raw=raw,
        )
