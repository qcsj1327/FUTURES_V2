from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any

from adapters.marketdata.base import MarketDataAdapter, MarketQuote, base_symbol


@dataclass
class SimulatedMarketDataV2(MarketDataAdapter):
    """
    Deterministic multi-symbol random walk market data.

    Canonical symbol is the base (e.g. "au"). Queries may use base symbols or
    trade aliases such as "au_main"; internal state stores base symbols only.
    """

    symbols: list[str]
    seed: int = 1
    start_prices: dict[str, float] = field(default_factory=dict)
    start_volumes: dict[str, float] = field(default_factory=dict)
    drift: float = 0.0
    vol: float = 0.01

    _t: int = 0
    _prices: dict[str, float] = field(default_factory=dict, init=False)
    _volumes: dict[str, float] = field(default_factory=dict, init=False)
    _rngs: dict[str, random.Random] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        bases = sorted({base_symbol(s) for s in self.symbols})
        self._prices = {}
        self._volumes = {}
        self._rngs = {}
        for s in bases:
            self._prices[s] = float(self.start_prices.get(s, 100.0))
            self._volumes[s] = float(self.start_volumes.get(s, 1000.0))
            self._rngs[s] = random.Random(self._seed_for_symbol(s))

    def _seed_for_symbol(self, symbol: str) -> int:
        return (self.seed * 1_000_003) ^ (sum(ord(c) for c in symbol) * 97)

    def advance(self) -> None:
        for s, p in list(self._prices.items()):
            z = self._rngs[s].gauss(0.0, 1.0)
            step = (self.drift - 0.5 * self.vol * self.vol) + (self.vol * z)
            self._prices[s] = max(0.0001, p * math.exp(step))
            self._volumes[s] = max(0.0, self._volumes[s] * (1.0 + abs(z) * 0.01))
        self._t += 1

    def get_last_quote(self, symbol: str) -> MarketQuote:
        key = base_symbol(symbol)
        if key not in self._prices:
            raise KeyError(f"symbol not in simulated universe: {symbol}")
        return MarketQuote(
            symbol=key,
            price=float(self._prices[key]),
            volume=float(self._volumes[key]),
            ts=self._t,
        )

    def get_last_quotes(self, symbols: list[str]) -> dict[str, MarketQuote]:
        out: dict[str, MarketQuote] = {}
        missing: list[str] = []
        for s in symbols:
            key = base_symbol(s)
            if key not in self._prices:
                missing.append(s)
            else:
                out[s] = self.get_last_quote(s)
        if missing:
            raise KeyError(f"missing symbols in simulated universe: {missing}")
        return out

    def snapshot(self) -> dict[str, Any]:
        return {"t": self._t, "prices": dict(self._prices), "volumes": dict(self._volumes)}
