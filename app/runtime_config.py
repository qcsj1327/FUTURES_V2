from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuntimeConfig:
    runtime_id: str = "r1"
    symbol: str = "au"
    instrument_id: str = "au"
    trade_instrument_id: str = "au_main"
    default_quantity: float = 1.0
