from __future__ import annotations

from dataclasses import dataclass, field

from adapters.marketdata.base import MarketQuote
from domain.signal import SignalDecision
from strategies.base.strategy import Strategy
from strategies.volume._common import RollingSeries, hold, mean, positive_float, positive_int


@dataclass
class VolumeGuard(Strategy):
    vol_window: int = 50
    min_vol_mult: float = 1.0
    _state: dict[str, RollingSeries] = field(default_factory=dict, init=False)

    @classmethod
    def from_params(cls, params: dict[str, object]) -> VolumeGuard:
        return cls(
            vol_window=positive_int(params.get("vol_window"), name="vol_window", default=50),
            min_vol_mult=positive_float(params.get("min_vol_mult"), default=1.0),
        )

    def _series(self, symbol: str) -> RollingSeries:
        if symbol not in self._state:
            self._state[symbol] = RollingSeries(maxlen=self.vol_window)
        return self._state[symbol]

    def generate(self, symbol: str, quote: MarketQuote) -> SignalDecision:
        series = self._series(symbol)
        if quote.volume is None:
            series.append(quote)
            return hold(
                strategy_name="volume_guard",
                symbol=symbol,
                quote=quote,
                reason="missing_volume",
            )

        if len(series.volumes) < self.vol_window:
            series.append(quote)
            return hold(
                strategy_name="volume_guard",
                symbol=symbol,
                quote=quote,
                reason="warming_up",
            )

        vol_ma = mean(series.volumes)
        blocked = quote.volume < vol_ma * self.min_vol_mult
        series.append(quote)
        return hold(
            strategy_name="volume_guard",
            symbol=symbol,
            quote=quote,
            reason="low_volume_blocked" if blocked else "volume_ok",
            raw={"vol_ma": vol_ma, "volume": quote.volume},
        )
