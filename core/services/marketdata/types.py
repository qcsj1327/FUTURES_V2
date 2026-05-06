from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


def base_symbol(symbol: str) -> str:
    return symbol[:-5] if symbol.endswith("_main") else symbol


@dataclass(frozen=True)
class MarketBar:
    open: float
    high: float
    low: float
    close: float
    volume: float
    ts: int | None


@dataclass(frozen=True)
class MarketQuote:
    symbol: str
    price: float
    volume: float | None
    ts: int | None
    bars: dict[str, MarketBar] = field(default_factory=dict)

    def get_bar(self, timeframe: str) -> MarketBar | None:
        return self.bars.get(timeframe)


class MarketDataAdapter(ABC):
    @abstractmethod
    def get_last_quote(self, symbol: str) -> MarketQuote:
        pass

    def get_last_quotes(self, symbols: list[str]) -> dict[str, MarketQuote]:
        return {s: self.get_last_quote(s) for s in symbols}
