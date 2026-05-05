from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adapters.marketdata.base import MarketBar, MarketDataAdapter, MarketQuote, base_symbol


@dataclass
class LiveFileMarketData(MarketDataAdapter):
    """
    Read-only market data adapter backed by a JSON quote file.

    Canonical format:
      {"au": {"price": 100.0, "volume": 1234.0, "ts": 1710000000}}

    Optional multi-timeframe bars:
      {
        "au": {
          "price": 100.0,
          "volume": 1234.0,
          "ts": 1710000000,
          "bars": {
            "5m": {
              "open": 99.0,
              "high": 101.0,
              "low": 98.5,
              "close": 100.0,
              "volume": 4321.0,
              "ts": 1710000000
            }
          }
        }
      }
    """

    prices_path: Path

    def _invalid_schema(self, symbol: str, reason: str) -> ValueError:
        return ValueError(f"invalid quote schema for symbol={symbol}: {reason}")

    def _number(self, symbol: str, payload: dict[str, Any], field: str) -> float:
        value = payload.get(field)
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise self._invalid_schema(symbol, f"{field} must be number")
        return float(value)

    def _ts(self, symbol: str, payload: dict[str, Any]) -> int:
        if "ts" not in payload:
            raise self._invalid_schema(symbol, "ts is required")
        ts_raw = payload["ts"]
        if ts_raw is not None and (
            not isinstance(ts_raw, int) or isinstance(ts_raw, bool)
        ):
            raise self._invalid_schema(symbol, "ts must be int|null")
        return 0 if ts_raw is None else ts_raw

    def _bar_from_payload(
        self,
        symbol: str,
        timeframe: str,
        payload: dict[str, Any],
    ) -> MarketBar:
        if not isinstance(timeframe, str) or not timeframe:
            raise self._invalid_schema(symbol, "bar timeframe must be non-empty string")
        return MarketBar(
            open=self._number(symbol, payload, "open"),
            high=self._number(symbol, payload, "high"),
            low=self._number(symbol, payload, "low"),
            close=self._number(symbol, payload, "close"),
            volume=self._number(symbol, payload, "volume"),
            ts=self._ts(symbol, payload),
        )

    def _bars_from_payload(
        self,
        symbol: str,
        payload: dict[str, Any],
    ) -> dict[str, MarketBar]:
        if "bars" not in payload:
            return {}
        bars_raw = payload["bars"]
        if not isinstance(bars_raw, dict):
            raise self._invalid_schema(symbol, "bars must be object")
        out: dict[str, MarketBar] = {}
        for timeframe, bar_payload in bars_raw.items():
            if not isinstance(timeframe, str):
                raise self._invalid_schema(symbol, "bar timeframe must be string")
            if not isinstance(bar_payload, dict):
                raise self._invalid_schema(symbol, f"bar {timeframe} must be object")
            out[timeframe] = self._bar_from_payload(symbol, timeframe, bar_payload)
        return out

    def _quote_from_payload(self, symbol: str, payload: dict[str, Any]) -> MarketQuote:
        if symbol.endswith("_main"):
            raise self._invalid_schema(symbol, "trade alias keys are not allowed")

        if "volume" not in payload:
            raise self._invalid_schema(symbol, "volume is required")

        return MarketQuote(
            symbol=base_symbol(symbol),
            price=self._number(symbol, payload, "price"),
            volume=self._number(symbol, payload, "volume"),
            ts=self._ts(symbol, payload),
            bars=self._bars_from_payload(symbol, payload),
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
