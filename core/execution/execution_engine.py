from __future__ import annotations

from adapters.broker.base import BrokerAdapter
from domain.enums import ExecutionStatus, PositionSide
from domain.execution import ExecutionOrder, ExecutionResult
from domain.risk import RiskDecision


class ExecutionEngine:
    def __init__(self, broker: BrokerAdapter) -> None:
        self.broker = broker

    def execute(self, decision: RiskDecision) -> tuple[ExecutionOrder | None, ExecutionResult]:
        if not decision.allowed:
            return None, ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                reason=decision.reason,
            )

        if decision.quantity is None:
            return None, ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                reason="missing_quantity",
            )

        if decision.quantity <= 0:
            return None, ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                reason="invalid_quantity",
            )

        order = ExecutionOrder(
            instrument_id=decision.instrument_id,
            trade_instrument_id=decision.trade_instrument_id,
            side=decision.side,
            position_side=decision.position_side or PositionSide.FLAT,
            quantity=decision.quantity,
            order_type="market",
        )

        result = self.broker.submit_order(order)

        return order, result
