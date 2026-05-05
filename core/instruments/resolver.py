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

    def roll_intent(self, symbol: str, ts: int) -> tuple[str, str] | None:
        return self._roll_policy.roll_intent(base_symbol(symbol), ts)

    def activate_roll(self, symbol: str, ts: int) -> tuple[str, str] | None:
        return self._roll_policy.activate_roll(base_symbol(symbol), ts)

    @property
    def roll_cooldown_ticks(self) -> int:
        return self._roll_policy.cooldown_ticks
