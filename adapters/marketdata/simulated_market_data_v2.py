from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from adapters.marketdata.base import MarketDataAdapter


@dataclass
class SimulatedMarketDataV2(MarketDataAdapter):
    """
    Deterministic multi-symbol random walk market data.
    - Prices evolve only when advance() is called.
    - Reproducible with seed.
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
        self._prices = {}
        self._rngs = {}
        for s in self.symbols:
            base = float(self.start_prices.get(s, 100.0))
            self._prices[s] = base
            self._rngs[s] = random.Random(self._seed_for_symbol(s))

    def _seed_for_symbol(self, symbol: str) -> int:
        # stable seed per symbol
        return (self.seed * 1_000_003) ^ (sum(ord(c) for c in symbol) * 97)

    def advance(self) -> None:
        # Geometric Brownian Motion-ish step:
        # p <- p * exp((drift - 0.5*vol^2) + vol*Z)
        for s, p in list(self._prices.items()):
            z = self._rngs[s].gauss(0.0, 1.0)
            step = (self.drift - 0.5 * self.vol * self.vol) + (self.vol * z)
            self._prices[s] = max(0.0001, p * math.exp(step))
        self._t += 1

    def get_last_price(self, symbol: str) -> float:
        if symbol not in self._prices:
            raise KeyError(f"symbol not in simulated universe: {symbol}")
        return float(self._prices[symbol])

    def get_last_prices(self, symbols: list[str]) -> dict[str, float]:
        missing = [s for s in symbols if s not in self._prices]
        if missing:
            raise KeyError(f"missing symbols in simulated universe: {missing}")
        return {s: float(self._prices[s]) for s in symbols}

    def snapshot(self) -> dict[str, Any]:
        return {"t": self._t, "prices": dict(self._prices)}
