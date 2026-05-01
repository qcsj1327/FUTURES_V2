from __future__ import annotations

from abc import ABC, abstractmethod


class MarketDataAdapter(ABC):
    @abstractmethod
    def get_last_price(self, symbol: str) -> float:
        pass

    def get_last_prices(self, symbols: list[str]) -> dict[str, float]:
        return {s: self.get_last_price(s) for s in symbols}
