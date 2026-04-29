from __future__ import annotations

import random

from adapters.marketdata.base import MarketDataAdapter


class SimulatedMarketData(MarketDataAdapter):
    def __init__(self) -> None:
        self._prices: dict[str, float] = {}

    def get_last_price(self, symbol: str) -> float:
        previous = self._prices.get(symbol, 100.0)

        drift = 0.03
        noise = random.uniform(-0.2, 0.2)
        price = max(previous + drift + noise, 0.01)

        self._prices[symbol] = price
        return float(price)
