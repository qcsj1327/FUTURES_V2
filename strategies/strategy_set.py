from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.signal import SignalDecision
from strategies.base.strategy import Strategy


@dataclass(frozen=True)
class StrategyEntry:
    name: str
    strategy: Strategy
    symbols: list[str]
    priority: int
    params: dict[str, Any]


class StrategySet:
    def __init__(self, entries: list[StrategyEntry]) -> None:
        # deterministic: sort by priority then name
        self.entries = sorted(entries, key=lambda e: (e.priority, e.name))

    def generate(self, prices: dict[str, float]) -> list[SignalDecision]:
        out: list[SignalDecision] = []
        for entry in self.entries:
            for sym in entry.symbols:
                if sym not in prices:
                    continue
                # strategy.generate(symbol, price) -> SignalDecision
                d = entry.strategy.generate(sym, prices[sym])
                out.append(d)
        return out
