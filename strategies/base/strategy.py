from __future__ import annotations

from abc import ABC, abstractmethod

from core.services.marketdata.types import MarketQuote
from domain.signal import SignalDecision


class Strategy(ABC):
    @abstractmethod
    def generate(self, symbol: str, quote: MarketQuote) -> SignalDecision:
        pass
