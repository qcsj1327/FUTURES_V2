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
            return self._reject("risk_not_allowed")

        if decision.decision is Decision.HOLD:
            return self._reject("hold_not_executable")

        if decision.quantity is None:
            return self._reject("missing_quantity")

        if decision.quantity <= 0:
            return self._reject("invalid_quantity")

        # ===== 合约约束 =====

        if decision.decision is Decision.OPEN_LONG:
            if decision.side is not Side.BUY or decision.position_side is not PositionSide.LONG:
                return self._reject("invalid_open_long_contract")

        if decision.decision is Decision.OPEN_SHORT:
            if decision.side is not Side.SELL or decision.position_side is not PositionSide.SHORT:
                return self._reject("invalid_open_short_contract")

        if decision.decision is Decision.CLOSE:
            if decision.side is Side.NONE:
                return self._reject("invalid_close_side")

        # 禁止 fallback
        if decision.position_side is None:
            return self._reject("missing_position_side")

        # ===== 合法才构造 order =====

        order = ExecutionOrder(
            instrument_id=decision.instrument_id,
            trade_instrument_id=decision.trade_instrument_id,
            side=decision.side,
            position_side=decision.position_side,
            quantity=decision.quantity,
            order_type="market",
        )

        result = self.broker.submit_order(order)

        return order, result

    @staticmethod
    def _reject(reason: str) -> tuple[None, ExecutionResult]:
        return None, ExecutionResult(
            success=False,
            status=ExecutionStatus.REJECTED,
            reason=reason,
        )