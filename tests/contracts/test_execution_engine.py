from __future__ import annotations

from core.execution.execution_engine import ExecutionEngine
from domain.enums import Decision, PositionSide, Side, TriggerLifecycle
from domain.risk import RiskDecision


def test_execution_engine_success() -> None:
    decision = RiskDecision(
        instrument_id="au",
        trade_instrument_id="au_main",
        allowed=True,
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        position_side=PositionSide.LONG,
        lifecycle=TriggerLifecycle.TRIGGERED,
        quantity=3.0,
    )

    order, result = ExecutionEngine().execute(decision)

    assert order is not None
    assert result.success is True
    assert order.quantity == 3.0
    assert order.instrument_id == "au"


def test_execution_engine_rejected() -> None:
    decision = RiskDecision(
        instrument_id="au",
        trade_instrument_id="au_main",
        allowed=False,
        decision=Decision.HOLD,
        side=Side.NONE,
        position_side=None,
        lifecycle=None,
    )

    order, result = ExecutionEngine().execute(decision)

    assert order is None
    assert result.success is False
