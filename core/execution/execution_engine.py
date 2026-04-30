from __future__ import annotations

from adapters.broker.base import BrokerAdapter
from domain.enums import Decision, ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult
from domain.risk import RiskDecision


class ExecutionEngine:
    def __init__(self, broker: BrokerAdapter) -> None:
        self.broker = broker

    def execute(self, decision: RiskDecision) -> tuple[ExecutionOrder | None, ExecutionResult]:
        if not decision.allowed:
            return None, self._rejected(decision.reason or "risk_not_allowed")

        if decision.decision == Decision.HOLD:
            return None, self._rejected("hold_not_executable")

        if decision.quantity is None:
            return None, self._rejected("missing_quantity")

        if decision.quantity <= 0:
            return None, self._rejected("invalid_quantity")

        if decision.position_side is None:
            return None, self._rejected("missing_position_side")

        if decision.decision == Decision.OPEN_LONG:
            if decision.side != Side.BUY or decision.position_side != PositionSide.LONG:
                return None, self._rejected("invalid_open_long_contract")

        if decision.decision == Decision.OPEN_SHORT:
            if decision.side != Side.SELL or decision.position_side != PositionSide.SHORT:
                return None, self._rejected("invalid_open_short_contract")

        if decision.decision == Decision.CLOSE:
            if decision.side == Side.NONE:
                return None, self._rejected("invalid_close_side")
            if decision.position_side == PositionSide.FLAT:
                return None, self._rejected("invalid_close_position_side")

        order = ExecutionOrder(
            instrument_id=decision.instrument_id,
            trade_instrument_id=decision.trade_instrument_id,
            side=decision.side,
            position_side=decision.position_side,
            quantity=decision.quantity,
            order_type="market",
            stop_loss=decision.stop_loss,
            take_profit=decision.take_profit,
        )

        result = self.broker.submit_order(order)
        return order, result

    def _rejected(self, reason: str) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            status=ExecutionStatus.REJECTED,
            reason=reason,
        )
