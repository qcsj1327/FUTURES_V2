from __future__ import annotations

from adapters.broker.base import BrokerAdapter
from domain.enums import ExecutionStatus
from domain.execution import ExecutionOrder, ExecutionResult


class FakeBroker(BrokerAdapter):
    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            status=ExecutionStatus.SUBMITTED,
            order_id="fake_order_1",
            reason="simulated_fill",
        )
