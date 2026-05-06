from __future__ import annotations

from adapters.broker.base import BrokerAdapter
from core.execution.execution_engine import ExecutionEngine
from core.execution.execution_request import ExecutionRequest
from core.execution.lifecycle_reasons import SIMULATED_FILL
from domain.enums import Decision, ExecutionStatus, PositionSide, Side, TriggerLifecycle
from domain.execution import ExecutionOrder, ExecutionResult
from domain.risk import RiskDecision


class RecordingBroker(BrokerAdapter):
    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            status=ExecutionStatus.SUBMITTED,
            order_id="recorded_order_1",
            reason=SIMULATED_FILL,
        )


def test_execution_engine_success() -> None:
    decision = RiskDecision(
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        allowed=True,
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        position_side=PositionSide.LONG,
        lifecycle=TriggerLifecycle.TRIGGERED,
        quantity=3.0,
    )

    order, result = ExecutionEngine(RecordingBroker()).execute(decision)

    assert order is not None
    assert result.success is True
    assert order.quantity == 3.0
    assert order.instrument_id == "au"
    assert result.order_id == "recorded_order_1"


def test_execution_engine_request_carries_order_price() -> None:
    decision = RiskDecision(
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        allowed=True,
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        position_side=PositionSide.LONG,
        lifecycle=TriggerLifecycle.TRIGGERED,
        quantity=3.0,
    )

    order, result = ExecutionEngine(RecordingBroker()).execute_request(
        ExecutionRequest(risk_decision=decision, order_price=450.0)
    )

    assert order is not None
    assert result.success is True
    assert order.price == 450.0


def test_execution_engine_rejected() -> None:
    decision = RiskDecision(
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        allowed=False,
        decision=Decision.HOLD,
        side=Side.NONE,
        position_side=None,
        lifecycle=None,
    )

    order, result = ExecutionEngine(RecordingBroker()).execute(decision)

    assert order is None
    assert result.success is False
