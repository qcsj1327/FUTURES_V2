from __future__ import annotations

from abc import ABC, abstractmethod


class MarketDataAdapter(ABC):
    @abstractmethod
    def get_last_price(self, symbol: str) -> float:
        pass
