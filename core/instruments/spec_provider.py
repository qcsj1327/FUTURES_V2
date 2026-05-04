from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


class InstrumentSpecProvider(Protocol):
    def load_overrides(self, *, base_symbols: list[str]) -> dict[str, dict[str, Any]]:
        """
        Return instrument spec override payloads keyed by base symbol.

        Allowed override keys must match core/instruments/specs.py::_apply_override:
        - tick_size
        - multiplier
        - margin_rate
        - commission_model
        - slippage_model
        """


def safe_float(x: object) -> float | None:
    if isinstance(x, bool):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    return None


def deep_merge(
    base: dict[str, dict[str, Any]],
    override: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {k: dict(v) for k, v in base.items()}
    for sym, payload in override.items():
        if sym not in out:
            out[sym] = dict(payload)
        else:
            out[sym].update(payload)
    return out


class StaticSpecProvider:
    def load_overrides(self, *, base_symbols: list[str]) -> dict[str, dict[str, Any]]:
        _ = base_symbols
        return {}


class TqKqSpecProvider:
    """
    Extract spec overrides from TqKq quote/instrument objects.

    This provider is read-only and only returns override payloads.
    It does not mutate any registry.
    """

    def __init__(
        self,
        *,
        tq_symbols: dict[str, str],
        quote_getter: Callable[[str], object],
    ) -> None:
        self._tq_symbols = dict(tq_symbols)
        self._get_quote = quote_getter

    def load_overrides(self, *, base_symbols: list[str]) -> dict[str, dict[str, Any]]:
        allowed = {"tick_size", "multiplier"}
        out: dict[str, dict[str, Any]] = {}
        for base in base_symbols:
            tq_sym = self._tq_symbols.get(base)
            if not tq_sym:
                continue
            q = self._get_quote(tq_sym)
            tick = safe_float(getattr(q, "price_tick", None))
            mult = safe_float(getattr(q, "volume_multiple", None))
            payload: dict[str, Any] = {}
            if tick is not None:
                payload["tick_size"] = tick
            if mult is not None:
                payload["multiplier"] = mult
            extra = set(payload) - allowed
            if extra:
                raise ValueError(f"tqkq provider returned unknown keys: {sorted(extra)}")
            if payload:
                out[base] = payload
        return out

