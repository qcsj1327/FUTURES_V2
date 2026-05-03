from __future__ import annotations

from dataclasses import is_dataclass, replace
from typing import Any

from adapters.marketdata.base import MarketQuote
from domain.enums import Decision
from domain.signal import SignalDecision
from strategies.base.strategy import Strategy


class ParametrizedStrategy(Strategy):
    """
    Wrap any Strategy and apply params deterministically.
    Supported params:
      - force_decision: "HOLD" | "OPEN_LONG" | "OPEN_SHORT" | "CLOSE" ...
      - by_symbol: { "au": {"force_decision": "HOLD"}, ... }
    """

    def __init__(self, *, strategy_name: str, base: Strategy, params: dict[str, Any]) -> None:
        self._name = strategy_name
        self._base = base
        self._params = dict(params)

    def generate(self, symbol: str, quote: MarketQuote) -> SignalDecision:
        d = self._base.generate(symbol, quote)

        by_symbol = self._params.get("by_symbol")
        if isinstance(by_symbol, dict):
            sym_params = by_symbol.get(symbol)
            if isinstance(sym_params, dict):
                return self._apply_params(d, sym_params)

        return self._apply_params(d, self._params)

    def _apply_params(self, d: SignalDecision, params: dict[str, Any]) -> SignalDecision:
        force = params.get("force_decision")
        if isinstance(force, str) and force:
            forced = Decision[force]  # KeyError if invalid
            if is_dataclass(d):
                return replace(d, decision=forced)
            try:
                d.decision = forced
            except Exception:
                pass
        return d
