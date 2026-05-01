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


@dataclass(frozen=True)
class TaggedDecision:
    strategy_name: str
    decision: SignalDecision


class StrategySet:
    def __init__(self, entries: list[StrategyEntry]) -> None:
        self.entries = sorted(entries, key=lambda e: (e.priority, e.name))

    def generate(self, prices: dict[str, float]) -> list[TaggedDecision]:
        out: list[TaggedDecision] = []
        for entry in self.entries:
            for sym in entry.symbols:
                if sym not in prices:
                    continue
                d = entry.strategy.generate(sym, prices[sym])
                out.append(TaggedDecision(strategy_name=entry.name, decision=d))
        return out
