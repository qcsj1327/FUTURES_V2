from __future__ import annotations

from core.execution.execution_engine import ExecutionEngine
from core.portfolio.portfolio_engine import PortfolioEngine
from core.risk.risk_engine import RiskEngine
from domain.enums import Decision, ExecutionStatus, PositionSide, Side, TriggerLifecycle
from domain.execution import ExecutionOrder, ExecutionResult
from domain.risk import RiskDecision
from domain.trigger import TriggerResult


class DummyBroker:
    def __init__(self) -> None:
        self.submitted = False

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        self.submitted = True
        return ExecutionResult(
            success=True,
            status=ExecutionStatus.SUBMITTED,
            order_id="order_1",
            fill_price=100.0,
        )


def test_risk_rejects_missing_instrument_without_fallback() -> None:
    trigger = TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id=None,
        trade_instrument_id="au2506",
    )

    result = RiskEngine().evaluate(PortfolioEngine().allocate(trigger, default_quantity=1.0))

    assert result.allowed is False
    assert result.instrument_id == ""
    assert result.trade_instrument_id == "au2506"
    assert result.reason == "missing_instrument_id"


def test_risk_rejects_missing_trade_instrument_without_fallback() -> None:
    trigger = TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="r1",
        instrument_id="au",
        trade_instrument_id=None,
    )

    result = RiskEngine().evaluate(PortfolioEngine().allocate(trigger, default_quantity=1.0))

    assert result.allowed is False
    assert result.instrument_id == "au"
    assert result.trade_instrument_id == ""
    assert result.reason == "missing_trade_instrument_id"


def test_risk_keeps_original_reason_when_not_triggered() -> None:
    trigger = TriggerResult(
        decision=Decision.HOLD,
        side=Side.NONE,
        lifecycle=TriggerLifecycle.BLOCKED,
        triggered=False,
        runtime_id="r1",
        reason="blocked",
    )

    result = RiskEngine().evaluate(PortfolioEngine().allocate(trigger, default_quantity=1.0))

    assert result.allowed is False
    assert result.quantity is None
    assert result.reason == "blocked"


def test_execution_does_not_execute_rejected_risk_decision() -> None:
    decision = RiskDecision(
        instrument_id="au",
        trade_instrument_id="au2506",
        allowed=False,
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        position_side=PositionSide.LONG,
        lifecycle=TriggerLifecycle.BLOCKED,
        quantity=None,
        reason="blocked",
    )

    broker = DummyBroker()
    engine = ExecutionEngine(broker)  # type: ignore[arg-type]

    order, result = engine.execute(decision)

    assert order is None
    assert result.success is False
    assert result.status == ExecutionStatus.REJECTED
    assert result.reason == "blocked"
    assert broker.submitted is False


def test_execution_rejects_allowed_decision_without_quantity() -> None:
    decision = RiskDecision(
        instrument_id="au",
        trade_instrument_id="au2506",
        allowed=True,
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        position_side=PositionSide.LONG,
        lifecycle=TriggerLifecycle.TRIGGERED,
        quantity=None,
        reason="bad_quantity",
    )

    broker = DummyBroker()
    engine = ExecutionEngine(broker)  # type: ignore[arg-type]

    order, result = engine.execute(decision)

    assert order is None
    assert result.success is False
    assert result.status == ExecutionStatus.REJECTED
    assert result.reason == "missing_quantity"
    assert broker.submitted is False
