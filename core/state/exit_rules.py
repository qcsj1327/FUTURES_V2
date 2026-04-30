from __future__ import annotations

from dataclasses import dataclass

from domain.enums import PositionSide
from domain.state import PositionState


@dataclass(frozen=True)
class ExitSignal:
    triggered: bool
    reason: str | None = None


class ExitRules:
    def evaluate(
        self,
        *,
        position: PositionState,
        current_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> ExitSignal:
        if position.quantity <= 0:
            return ExitSignal(triggered=False)

        if position.avg_price is None:
            raise ValueError("position_avg_price_required")

        if position.position_side == PositionSide.LONG:
            return self._evaluate_long(
                current_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

        if position.position_side == PositionSide.SHORT:
            return self._evaluate_short(
                current_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )

        return ExitSignal(triggered=False)

    def _evaluate_long(
        self,
        *,
        current_price: float,
        stop_loss: float | None,
        take_profit: float | None,
    ) -> ExitSignal:
        if stop_loss is not None and current_price <= stop_loss:
            return ExitSignal(triggered=True, reason="stop_loss")

        if take_profit is not None and current_price >= take_profit:
            return ExitSignal(triggered=True, reason="take_profit")

        return ExitSignal(triggered=False)

    def _evaluate_short(
        self,
        *,
        current_price: float,
        stop_loss: float | None,
        take_profit: float | None,
    ) -> ExitSignal:
        if stop_loss is not None and current_price >= stop_loss:
            return ExitSignal(triggered=True, reason="stop_loss")

        if take_profit is not None and current_price <= take_profit:
            return ExitSignal(triggered=True, reason="take_profit")

        return ExitSignal(triggered=False)
