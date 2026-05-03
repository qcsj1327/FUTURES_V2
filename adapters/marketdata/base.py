from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


def base_symbol(symbol: str) -> str:
    return symbol[:-5] if symbol.endswith("_main") else symbol


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    price: float
    volume: float | None
    ts: int


class MarketDataAdapter(ABC):
    @abstractmethod
    def get_last_quote(self, symbol: str) -> MarketQuote:
        pass

    def get_last_quotes(self, symbols: list[str]) -> dict[str, MarketQuote]:
        return {s: self.get_last_quote(s) for s in symbols}
