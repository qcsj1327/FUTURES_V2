from __future__ import annotations

from domain.enums import Side


class SlippageModel:
    def __init__(self, slippage_rate: float = 0.0) -> None:
        if slippage_rate < 0:
            raise ValueError("slippage_rate_must_be_non_negative")

        self.slippage_rate = slippage_rate

    def apply(self, *, market_price: float, side: Side) -> float:
        if side == Side.BUY:
            return market_price * (1 + self.slippage_rate)

        if side == Side.SELL:
            return market_price * (1 - self.slippage_rate)

        return market_price
