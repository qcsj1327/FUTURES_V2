from __future__ import annotations

from dataclasses import dataclass

from config.instrument_universe import default_symbols, trade_contracts_for

_DEFAULT_SYMBOL = default_symbols()[0]
_DEFAULT_TRADE_CONTRACT = trade_contracts_for([_DEFAULT_SYMBOL])[_DEFAULT_SYMBOL]


@dataclass(frozen=True)
class RuntimeConfig:
    runtime_id: str = "r1"
    symbol: str = _DEFAULT_SYMBOL
    instrument_id: str = _DEFAULT_SYMBOL
    trade_instrument_id: str = _DEFAULT_TRADE_CONTRACT
    default_quantity: float = 1.0
    stop_loss: float | None = None
    take_profit: float | None = None
    stop_loss_pct: float | None = None
    take_profit_pct: float | None = None
    dynamic_exit_enabled: bool = True
    dynamic_stop_loss_vol_mult: float = 3.0
    dynamic_take_profit_vol_mult: float = 5.0
    dynamic_min_stop_loss_pct: float = 0.006
    dynamic_min_take_profit_pct: float = 0.012
    dynamic_max_stop_loss_pct: float = 0.03
    dynamic_max_take_profit_pct: float = 0.06
