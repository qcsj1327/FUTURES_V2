from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from adapters.marketdata.base import MarketDataAdapter


def _base_symbol(symbol: str) -> str:
    return symbol[:-5] if symbol.endswith("_main") else symbol


@dataclass
class LiveFileMarketData(MarketDataAdapter):
    """
    Read-only 'live' market data adapter backed by a JSON file.

    Preferred file format (canonical):
      {"au": 100.0, "ag": 50.0}

    Alias semantics:
      - "au_main" is treated as an alias of "au"
      - If both "au" and "au_main" exist in the file, they must be equal.
    """

    prices_path: Path

    def _read_prices(self) -> dict[str, float]:
        data = json.loads(self.prices_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("prices file must be a JSON object")

        out: dict[str, float] = {}
        for k, v in data.items():
            if not isinstance(k, str):
                continue
            if isinstance(v, (int, float)):
                out[k] = float(v)

        # If both base and *_main are present, enforce equality (no pollution).
        for k, v in list(out.items()):
            if k.endswith("_main"):
                base = _base_symbol(k)
                if base in out and out[base] != v:
                    raise ValueError(f"price mismatch: {base}={out[base]} vs {k}={v}")
        return out

    def _resolve_one(self, prices: dict[str, float], symbol: str) -> float:
        if symbol in prices:
            return prices[symbol]

        base = _base_symbol(symbol)
        alt = base if symbol.endswith("_main") else f"{symbol}_main"

        if alt in prices:
            return prices[alt]
        if base in prices:
            return prices[base]

        raise KeyError(f"missing price for symbol={symbol}")

    def get_last_price(self, symbol: str) -> float:
        prices = self._read_prices()
        return self._resolve_one(prices, symbol)

    def get_last_prices(self, symbols: list[str]) -> dict[str, float]:
        prices = self._read_prices()
        out: dict[str, float] = {}
        missing: list[str] = []
        for s in symbols:
            try:
                out[s] = self._resolve_one(prices, s)
            except KeyError:
                missing.append(s)
        if missing:
            raise KeyError(f"missing prices: {missing}")
        return out
