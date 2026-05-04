from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any


@dataclass(frozen=True)
class CommissionModel:
    mode: str
    value: float


@dataclass(frozen=True)
class SlippageModel:
    mode: str
    value: float


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    tick_size: float
    multiplier: float
    min_qty: float | None
    commission_model: CommissionModel
    slippage_model: SlippageModel
    margin_rate: float | None = None


_DEFAULT_SPECS: dict[str, InstrumentSpec] = {
    "au": InstrumentSpec(
        symbol="au",
        tick_size=0.02,
        multiplier=1000.0,
        min_qty=1.0,
        commission_model=CommissionModel(mode="fixed_per_order", value=10.0),
        slippage_model=SlippageModel(mode="ticks", value=1.0),
        margin_rate=0.10,
    ),
    "ag": InstrumentSpec(
        symbol="ag",
        tick_size=1.0,
        multiplier=15.0,
        min_qty=1.0,
        commission_model=CommissionModel(mode="bps_notional", value=0.5),
        slippage_model=SlippageModel(mode="ticks", value=1.0),
        margin_rate=0.12,
    ),
    "cu": InstrumentSpec(
        symbol="cu",
        tick_size=10.0,
        multiplier=5.0,
        min_qty=1.0,
        commission_model=CommissionModel(mode="bps_notional", value=0.5),
        slippage_model=SlippageModel(mode="ticks", value=1.0),
        margin_rate=0.12,
    ),
    "rb": InstrumentSpec(
        symbol="rb",
        tick_size=1.0,
        multiplier=10.0,
        min_qty=1.0,
        commission_model=CommissionModel(mode="bps_notional", value=1.0),
        slippage_model=SlippageModel(mode="ticks", value=1.0),
        margin_rate=0.10,
    ),
    "zn": InstrumentSpec(
        symbol="zn",
        tick_size=5.0,
        multiplier=5.0,
        min_qty=1.0,
        commission_model=CommissionModel(mode="bps_notional", value=0.5),
        slippage_model=SlippageModel(mode="ticks", value=1.0),
        margin_rate=0.12,
    ),
}


class InstrumentSpecRegistry:
    def __init__(self, specs: dict[str, InstrumentSpec] | None = None) -> None:
        self._specs = dict(specs or _DEFAULT_SPECS)

    @classmethod
    def with_overrides(cls, overrides: dict[str, dict[str, Any]]) -> InstrumentSpecRegistry:
        registry = cls()
        for symbol, payload in overrides.items():
            registry._specs[symbol] = _apply_override(registry.get(symbol), payload)
        return registry

    def get(self, symbol: str) -> InstrumentSpec:
        base = symbol[:-5] if symbol.endswith("_main") else symbol
        spec = self._specs.get(base)
        if spec is None:
            raise KeyError(f"missing instrument spec for symbol={base}")
        return spec

    def specs_for(self, base_symbols: list[str]) -> dict[str, InstrumentSpec]:
        return {sym: self.get(sym) for sym in base_symbols}


def _apply_override(spec: InstrumentSpec, payload: dict[str, Any]) -> InstrumentSpec:
    allowed = {
        "tick_size",
        "multiplier",
        "margin_rate",
        "commission_model",
        "slippage_model",
    }
    extra = set(payload) - allowed
    if extra:
        raise ValueError(f"unknown instrument spec override keys: {sorted(extra)}")

    commission = spec.commission_model
    raw_commission = payload.get("commission_model")
    if raw_commission is not None:
        commission = _parse_commission(raw_commission)

    slippage = spec.slippage_model
    raw_slippage = payload.get("slippage_model")
    if raw_slippage is not None:
        slippage = _parse_slippage(raw_slippage)

    tick_size = float(payload.get("tick_size", spec.tick_size))
    multiplier = float(payload.get("multiplier", spec.multiplier))
    margin_rate_raw = payload.get("margin_rate", spec.margin_rate)
    margin_rate = None if margin_rate_raw is None else float(margin_rate_raw)
    return replace(
        spec,
        tick_size=tick_size,
        multiplier=multiplier,
        commission_model=commission,
        slippage_model=slippage,
        margin_rate=margin_rate,
    )


def _parse_commission(payload: Any) -> CommissionModel:
    if not isinstance(payload, dict):
        raise ValueError("commission_model must be object")
    mode = str(payload.get("mode", ""))
    if mode not in {"fixed_per_order", "per_qty", "bps_notional"}:
        raise ValueError(f"invalid commission_model.mode: {mode}")
    return CommissionModel(mode=mode, value=float(payload.get("value", 0.0)))


def _parse_slippage(payload: Any) -> SlippageModel:
    if not isinstance(payload, dict):
        raise ValueError("slippage_model must be object")
    mode = str(payload.get("mode", ""))
    if mode not in {"bps", "ticks"}:
        raise ValueError(f"invalid slippage_model.mode: {mode}")
    return SlippageModel(mode=mode, value=float(payload.get("value", 0.0)))
