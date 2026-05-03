from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from adapters.marketdata.base import MarketQuote
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
    strategy_impl: str = "unknown"


class StrategySet:
    def __init__(self, entries: list[StrategyEntry]) -> None:
        self.entries = sorted(entries, key=lambda e: (e.priority, e.name))

    def _impl_name(self, s: Strategy) -> str:
        base = getattr(s, "_base", None)
        if base is not None:
            return str(base.__class__.__name__)
        return str(s.__class__.__name__)

    def generate(self, quotes: dict[str, MarketQuote]) -> list[TaggedDecision]:
        out: list[TaggedDecision] = []
        for entry in self.entries:
            impl = self._impl_name(entry.strategy)
            for sym in entry.symbols:
                if sym not in quotes:
                    continue
                d = entry.strategy.generate(sym, quotes[sym])
                out.append(TaggedDecision(entry.name, d, impl))
        return out
