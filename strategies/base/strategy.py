from __future__ import annotations

from abc import ABC, abstractmethod

from domain.signal import SignalDecision


class Strategy(ABC):
    @abstractmethod
    def generate(self, symbol: str, price: float) -> SignalDecision:
        pass
