from __future__ import annotations

from domain.enums import ExecutionStatus, PositionSide
from domain.execution import ExecutionOrder, ExecutionResult
from domain.risk import RiskDecision


class ExecutionEngine:
    def execute(self, decision: RiskDecision) -> tuple[ExecutionOrder | None, ExecutionResult]:
        if not decision.allowed:
            return None, ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                reason=decision.reason,
            )

        order = ExecutionOrder(
            instrument_id=decision.instrument_id,
            trade_instrument_id=decision.trade_instrument_id,
            side=decision.side,
            position_side=decision.position_side or PositionSide.FLAT,
            quantity=decision.quantity or 0.0,
            order_type="market",
        )

        result = ExecutionResult(
            success=True,
            status=ExecutionStatus.SUBMITTED,
        )

        return order, result
