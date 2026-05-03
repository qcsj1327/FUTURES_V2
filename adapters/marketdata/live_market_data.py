from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adapters.marketdata.base import MarketDataAdapter, MarketQuote, base_symbol


@dataclass
class LiveFileMarketData(MarketDataAdapter):
    """
    Read-only market data adapter backed by a JSON quote file.

    Canonical format:
      {"au": {"price": 100.0, "volume": 1234.0, "ts": 1710000000}}
    """

    prices_path: Path

    def _quote_from_payload(self, symbol: str, payload: dict[str, Any]) -> MarketQuote:
        price = payload.get("price")
        if not isinstance(price, (int, float)):
            raise ValueError(f"quote.price required for symbol={symbol}")

        if "volume" not in payload:
            raise ValueError(f"quote.volume required for symbol={symbol}")
        volume = payload["volume"]
        if volume is not None and not isinstance(volume, (int, float)):
            raise ValueError(f"quote.volume must be number|null for symbol={symbol}")

        ts = payload.get("ts")
        if not isinstance(ts, int):
            raise ValueError(f"quote.ts required for symbol={symbol}")

        return MarketQuote(
            symbol=base_symbol(symbol),
            price=float(price),
            volume=None if volume is None else float(volume),
            ts=ts,
        )

    def _read_quotes(self) -> dict[str, MarketQuote]:
        data = json.loads(self.prices_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("market data file must be a JSON object")

        out: dict[str, MarketQuote] = {}
        for k, v in data.items():
            if isinstance(k, str) and isinstance(v, dict):
                out[k] = self._quote_from_payload(k, v)

        for k, quote in list(out.items()):
            if k.endswith("_main"):
                base = base_symbol(k)
                if base in out and out[base] != quote:
                    raise ValueError(f"quote mismatch: {base}={out[base]} vs {k}={quote}")
        return out

    def _resolve_one(self, quotes: dict[str, MarketQuote], symbol: str) -> MarketQuote:
        if symbol in quotes:
            return quotes[symbol]

        base = base_symbol(symbol)
        alt = base if symbol.endswith("_main") else f"{symbol}_main"

        if alt in quotes:
            return quotes[alt]
        if base in quotes:
            return quotes[base]

        raise KeyError(f"missing quote for symbol={symbol}")

    def get_last_quote(self, symbol: str) -> MarketQuote:
        quotes = self._read_quotes()
        return self._resolve_one(quotes, symbol)

    def get_last_quotes(self, symbols: list[str]) -> dict[str, MarketQuote]:
        quotes = self._read_quotes()
        out: dict[str, MarketQuote] = {}
        missing: list[str] = []
        for s in symbols:
            try:
                out[s] = self._resolve_one(quotes, s)
            except KeyError:
                missing.append(s)
        if missing:
            raise KeyError(f"missing quotes: {missing}")
        return out
