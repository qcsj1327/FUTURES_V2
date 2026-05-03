from __future__ import annotations

from core.instruments.calendar import base_symbol
from core.instruments.roll_policy import RollPolicy


class InstrumentResolver:
    def __init__(self, *, roll_policy: RollPolicy) -> None:
        self._roll_policy = roll_policy

    def base_symbol(self, symbol: str) -> str:
        return base_symbol(symbol)

    def resolve_trade_instrument_id(self, symbol: str, ts: int) -> str:
        return self._roll_policy.resolve(base_symbol(symbol), ts)
