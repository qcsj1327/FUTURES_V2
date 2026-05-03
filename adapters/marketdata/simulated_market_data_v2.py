from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from adapters.marketdata.base import MarketDataAdapter


def _base_symbol(symbol: str) -> str:
    return symbol[:-5] if symbol.endswith("_main") else symbol


@dataclass
class SimulatedMarketDataV2(MarketDataAdapter):
    """
    Deterministic multi-symbol random walk market data.
    - Symbols must include any trade instruments (e.g. *_main) you plan to query.
    - This adapter does NOT alias base symbols to *_main.


    Canonical symbol is the base (e.g. "au").
    Alias semantics:
      - internal state only stores base symbols
    """

    symbols: list[str]
    seed: int = 1
    start_prices: dict[str, float] = field(default_factory=dict)
    drift: float = 0.0
    vol: float = 0.01

    _t: int = 0
    _prices: dict[str, float] = field(default_factory=dict, init=False)
    _rngs: dict[str, random.Random] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        bases = sorted({_base_symbol(s) for s in self.symbols})
        self._prices = {}
        self._rngs = {}
        for s in bases:
            base = float(self.start_prices.get(s, 100.0))
            self._prices[s] = base
            self._rngs[s] = random.Random(self._seed_for_symbol(s))

    def _seed_for_symbol(self, symbol: str) -> int:
        return (self.seed * 1_000_003) ^ (sum(ord(c) for c in symbol) * 97)

    def advance(self) -> None:
        for s, p in list(self._prices.items()):
            z = self._rngs[s].gauss(0.0, 1.0)
            step = (self.drift - 0.5 * self.vol * self.vol) + (self.vol * z)
            self._prices[s] = max(0.0001, p * math.exp(step))
        self._t += 1

    def get_last_price(self, symbol: str) -> float:
        key = _base_symbol(symbol)
        if key not in self._prices:
            raise KeyError(f"symbol not in simulated universe: {symbol}")
        return float(self._prices[key])

    def get_last_prices(self, symbols: list[str]) -> dict[str, float]:
        out: dict[str, float] = {}
        missing: list[str] = []
        for s in symbols:
            key = _base_symbol(s)
            if key not in self._prices:
                missing.append(s)
            else:
                out[s] = float(self._prices[key])
        if missing:
            raise KeyError(f"missing symbols in simulated universe: {missing}")
        return out

    def snapshot(self) -> dict[str, Any]:
        return {"t": self._t, "prices": dict(self._prices)}
