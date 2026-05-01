from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from adapters.marketdata.base import MarketDataAdapter


@dataclass
class LiveFileMarketData(MarketDataAdapter):
    """
    Read-only 'live' market data adapter backed by a JSON file.

    File format:
      {"au": 100.0, "ag": 50.0, ...}

    External process can update this file continuously from real market feeds.
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
        return out

    def get_last_price(self, symbol: str) -> float:
        prices = self._read_prices()
        if symbol not in prices:
            raise KeyError(f"missing price for symbol={symbol}")
        return prices[symbol]

    def get_last_prices(self, symbols: list[str]) -> dict[str, float]:
        prices = self._read_prices()
        missing = [s for s in symbols if s not in prices]
        if missing:
            raise KeyError(f"missing prices: {missing}")
        return {s: prices[s] for s in symbols}
