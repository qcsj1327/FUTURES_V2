from __future__ import annotations

from core.services.trade.exit_rules import ExitSignal
from domain.enums import PositionSide, Side
from domain.execution import ExecutionOrder
from domain.state import PositionState


class ExitOrderFactory:
    def create(
        self,
        *,
        position: PositionState,
        signal: ExitSignal,
    ) -> ExecutionOrder | None:
        if not signal.triggered:
            return None

        if position.quantity <= 0:
            return None

        side = self._exit_side(position.position_side)

        return ExecutionOrder(
            instrument_id=position.instrument_id,
            trade_instrument_id=position.trade_instrument_id,
            side=side,
            position_side=position.position_side,
            quantity=position.quantity,
            order_type="market",
        )

    def _exit_side(self, position_side: PositionSide) -> Side:
        if position_side == PositionSide.LONG:
            return Side.SELL

        if position_side == PositionSide.SHORT:
            return Side.BUY

        raise ValueError("flat_position_cannot_exit")
