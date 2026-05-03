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

    def _invalid_schema(self, symbol: str, reason: str) -> ValueError:
        return ValueError(f"invalid quote schema for symbol={symbol}: {reason}")

    def _quote_from_payload(self, symbol: str, payload: dict[str, Any]) -> MarketQuote:
        if symbol.endswith("_main"):
            raise self._invalid_schema(symbol, "trade alias keys are not allowed")

        price = payload.get("price")
        if not isinstance(price, (int, float)):
            raise self._invalid_schema(symbol, "price must be number")

        if "volume" not in payload:
            raise self._invalid_schema(symbol, "volume is required")
        volume = payload["volume"]
        if not isinstance(volume, (int, float)):
            raise self._invalid_schema(symbol, "volume must be number")

        if "ts" not in payload:
            raise self._invalid_schema(symbol, "ts is required")
        ts_raw = payload["ts"]
        if ts_raw is not None and not isinstance(ts_raw, int):
            raise self._invalid_schema(symbol, "ts must be int|null")

        return MarketQuote(
            symbol=base_symbol(symbol),
            price=float(price),
            volume=float(volume),
            ts=0 if ts_raw is None else ts_raw,
        )

    def _read_quotes(self) -> dict[str, MarketQuote]:
        data = json.loads(self.prices_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("market data file must be a JSON object")

        out: dict[str, MarketQuote] = {}
        for k, v in data.items():
            if not isinstance(k, str):
                continue
            if not isinstance(v, dict):
                raise self._invalid_schema(k, "quote must be object")
            out[k] = self._quote_from_payload(k, v)
        return out

    def _resolve_one(self, quotes: dict[str, MarketQuote], symbol: str) -> MarketQuote:
        base = base_symbol(symbol)
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
