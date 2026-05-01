from __future__ import annotations

from core.services.trade.exit_order_factory import ExitOrderFactory
from core.services.trade.exit_rules import ExitRules
from domain.execution import ExecutionOrder
from domain.state import PositionState


class ExitService:
    def __init__(self) -> None:
        self.exit_rules = ExitRules()
        self.exit_order_factory = ExitOrderFactory()

    def create_exit_order(
        self,
        *,
        position: PositionState,
        current_price: float,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> ExecutionOrder | None:
        signal = self.exit_rules.evaluate(
            position=position,
            current_price=current_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

        return self.exit_order_factory.create(
            position=position,
            signal=signal,
        )
