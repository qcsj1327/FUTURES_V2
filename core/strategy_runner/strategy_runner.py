from __future__ import annotations

from core.services.marketdata.types import MarketQuote
from domain.signal import SignalDecision
from strategies.registry import StrategyRegistry


class StrategyRunner:
    def __init__(self, registry: StrategyRegistry) -> None:
        self.registry = registry

    def run(self, symbol: str, quote: MarketQuote) -> list[SignalDecision]:
        signals: list[SignalDecision] = []

        for strategy in self.registry.all().values():
            signal = strategy.generate(symbol, quote)
            signals.append(signal)

        return signals
