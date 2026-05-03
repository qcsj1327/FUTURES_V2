from __future__ import annotations

import time

from adapters.marketdata.base import MarketDataAdapter, MarketQuote, base_symbol


class SimulatedMarketData(MarketDataAdapter):
    def __init__(self) -> None:
        self._prices: dict[str, float] = {}
        self._volumes: dict[str, float] = {}

    def get_last_quote(self, symbol: str) -> MarketQuote:
        key = base_symbol(symbol)
        previous = self._prices.get(key, 100.0)

        drift = 0.03
        price = max(previous + drift, 0.01)
        volume = self._volumes.get(key, 1000.0) + 10.0

        self._prices[key] = price
        self._volumes[key] = volume
        return MarketQuote(
            symbol=key,
            price=float(price),
            volume=float(volume),
            ts=int(time.time()),
        )

    def snapshot_prices(self) -> dict[str, float]:
        return dict(self._prices)

    def get_last_quotes(self, symbols: list[str]) -> dict[str, MarketQuote]:
        return {s: self.get_last_quote(s) for s in symbols}
