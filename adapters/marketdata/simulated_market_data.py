from __future__ import annotations

from adapters.marketdata.base import MarketDataAdapter


class SimulatedMarketData(MarketDataAdapter):
    def __init__(self) -> None:
        self._prices: dict[str, float] = {}

    def get_last_price(self, symbol: str) -> float:
        previous = self._prices.get(symbol, 100.0)

        drift = 0.03
        price = max(previous + drift, 0.01)

        self._prices[symbol] = price
        return float(price)

    def snapshot_prices(self) -> dict[str, float]:
        return dict(self._prices)
