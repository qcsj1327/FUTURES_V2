from __future__ import annotations

from dataclasses import dataclass, field

from core.services.marketdata.types import MarketQuote
from domain.enums import Decision, SignalStrength
from domain.signal import SignalDecision
from strategies.base.strategy import Strategy
from strategies.volume._common import (
    RollingSeries,
    hold,
    mean,
    quote_for_timeframe,
    signal,
    stdev,
    strict_positive_float,
    strict_positive_int,
    strict_timeframe,
)


@dataclass
class VolumeMAReversion(Strategy):
    window: int = 50
    z_entry: float = 2.0
    z_exit: float = 0.5
    low_vol_mult: float = 0.8
    timeframe: str = "spot"
    _state: dict[str, RollingSeries] = field(default_factory=dict, init=False)
    _position: dict[str, int] = field(default_factory=dict, init=False)

    @classmethod
    def from_params(cls, params: dict[str, object]) -> VolumeMAReversion:
        return cls(
            window=strict_positive_int(params, "window"),
            z_entry=strict_positive_float(params, "z_entry"),
            z_exit=strict_positive_float(params, "z_exit"),
            low_vol_mult=strict_positive_float(params, "low_vol_mult"),
            timeframe=strict_timeframe(params),
        )

    def _series(self, symbol: str) -> RollingSeries:
        if symbol not in self._state:
            self._state[symbol] = RollingSeries(maxlen=self.window)
        return self._state[symbol]

    def generate(self, symbol: str, quote: MarketQuote) -> SignalDecision:
        try:
            quote = quote_for_timeframe(quote, self.timeframe)
        except KeyError:
            return hold(
                strategy_name="volume_ma_reversion",
                symbol=symbol,
                quote=quote,
                reason="missing_timeframe_bar",
                raw={"timeframe": self.timeframe},
            )
        series = self._series(symbol)
        if quote.volume is None:
            series.append(quote)
            return hold(
                strategy_name="volume_ma_reversion",
                symbol=symbol,
                quote=quote,
                reason="missing_volume",
            )

        if len(series.prices) < self.window or len(series.volumes) < self.window:
            series.append(quote)
            return hold(
                strategy_name="volume_ma_reversion",
                symbol=symbol,
                quote=quote,
                reason="warming_up",
            )

        price_ma = mean(series.prices)
        price_std = stdev(series.prices)
        vol_ma = mean(series.volumes)
        z = 0.0 if price_std == 0.0 else (quote.price - price_ma) / price_std
        low_volume = quote.volume < vol_ma * self.low_vol_mult
        pos = self._position.get(symbol, 0)
        raw = {
            "price_ma": price_ma,
            "price_std": price_std,
            "vol_ma": vol_ma,
            "z": z,
            "timeframe": self.timeframe,
        }
        series.append(quote)

        if pos != 0 and abs(z) <= self.z_exit:
            self._position[symbol] = 0
            return signal(
                strategy_name="volume_ma_reversion",
                symbol=symbol,
                quote=quote,
                decision=Decision.CLOSE,
                reason="reversion_exit",
                confidence=0.7,
                strength=SignalStrength.MEDIUM,
                raw=raw,
            )
        if pos == 0 and low_volume and z >= self.z_entry:
            self._position[symbol] = -1
            return signal(
                strategy_name="volume_ma_reversion",
                symbol=symbol,
                quote=quote,
                decision=Decision.OPEN_SHORT,
                reason="low_volume_high_z_reversion",
                confidence=0.8,
                strength=SignalStrength.MEDIUM,
                raw=raw,
            )
        if pos == 0 and low_volume and z <= -self.z_entry:
            self._position[symbol] = 1
            return signal(
                strategy_name="volume_ma_reversion",
                symbol=symbol,
                quote=quote,
                decision=Decision.OPEN_LONG,
                reason="low_volume_low_z_reversion",
                confidence=0.8,
                strength=SignalStrength.MEDIUM,
                raw=raw,
            )
        return hold(
            strategy_name="volume_ma_reversion",
            symbol=symbol,
            quote=quote,
            reason="no_reversion",
            raw=raw,
        )
