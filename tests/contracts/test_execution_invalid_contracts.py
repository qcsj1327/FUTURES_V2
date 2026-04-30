from __future__ import annotations

from adapters.broker.base import BrokerAdapter
from core.execution.execution_engine import ExecutionEngine
from domain.enums import Decision, ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult
from domain.risk import RiskDecision


class DummyBroker(BrokerAdapter):
    def __init__(self) -> None:
        self.calls = 0
        self.last_order: ExecutionOrder | None = None

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        self.calls += 1
        self.last_order = order
        return ExecutionResult(
            success=True,
            status=ExecutionStatus.SUBMITTED,
            order_id="order_1",
        )


def make_decision(
    *,
    allowed: bool = True,
    decision: Decision = Decision.OPEN_LONG,
    side: Side = Side.BUY,
    position_side: PositionSide | None = PositionSide.LONG,
    quantity: float | None = 1.0,
) -> RiskDecision:
    return RiskDecision(
        instrument_id="au",
        trade_instrument_id="au2506",
        allowed=allowed,
        decision=decision,
        side=side,
        position_side=position_side,
        lifecycle=None,
        quantity=quantity,
        reason="source_reason",
    )


def test_allowed_false_rejected_without_broker_call() -> None:
    broker = DummyBroker()
    order, result = ExecutionEngine(broker).execute(make_decision(allowed=False))

    assert order is None
    assert result.status == ExecutionStatus.REJECTED
    assert result.reason == "source_reason"
    assert broker.calls == 0


def test_hold_rejected_without_broker_call() -> None:
    broker = DummyBroker()
    order, result = ExecutionEngine(broker).execute(
        make_decision(decision=Decision.HOLD, side=Side.NONE, position_side=PositionSide.FLAT)
    )

    assert order is None
    assert result.reason == "hold_not_executable"
    assert broker.calls == 0


def test_missing_quantity_rejected_without_fallback() -> None:
    broker = DummyBroker()
    order, result = ExecutionEngine(broker).execute(make_decision(quantity=None))

    assert order is None
    assert result.reason == "missing_quantity"
    assert broker.calls == 0


def test_invalid_quantity_rejected_without_fallback() -> None:
    broker = DummyBroker()
    order, result = ExecutionEngine(broker).execute(make_decision(quantity=0.0))

    assert order is None
    assert result.reason == "invalid_quantity"
    assert broker.calls == 0


def test_missing_position_side_rejected_without_fallback() -> None:
    broker = DummyBroker()
    order, result = ExecutionEngine(broker).execute(make_decision(position_side=None))

    assert order is None
    assert result.reason == "missing_position_side"
    assert broker.calls == 0


def test_open_long_requires_buy_and_long() -> None:
    broker = DummyBroker()
    order, result = ExecutionEngine(broker).execute(
        make_decision(decision=Decision.OPEN_LONG, side=Side.SELL, position_side=PositionSide.LONG)
    )

    assert order is None
    assert result.reason == "invalid_open_long_contract"
    assert broker.calls == 0


def test_open_short_requires_sell_and_short() -> None:
    broker = DummyBroker()
    order, result = ExecutionEngine(broker).execute(
        make_decision(decision=Decision.OPEN_SHORT, side=Side.BUY, position_side=PositionSide.SHORT)
    )

    assert order is None
    assert result.reason == "invalid_open_short_contract"
    assert broker.calls == 0


def test_close_rejects_none_side() -> None:
    broker = DummyBroker()
    order, result = ExecutionEngine(broker).execute(
        make_decision(decision=Decision.CLOSE, side=Side.NONE, position_side=PositionSide.LONG)
    )

    assert order is None
    assert result.reason == "invalid_close_side"
    assert broker.calls == 0


def test_close_rejects_flat_position_side() -> None:
    broker = DummyBroker()
    order, result = ExecutionEngine(broker).execute(
        make_decision(decision=Decision.CLOSE, side=Side.SELL, position_side=PositionSide.FLAT)
    )

    assert order is None
    assert result.reason == "invalid_close_position_side"
    assert broker.calls == 0


def test_valid_decision_calls_broker_once() -> None:
    broker = DummyBroker()
    order, result = ExecutionEngine(broker).execute(make_decision())

    assert order is not None
    assert result.status == ExecutionStatus.SUBMITTED
    assert broker.calls == 1
    assert broker.last_order == order
    assert order.quantity == 1.0
    assert order.position_side == PositionSide.LONG
