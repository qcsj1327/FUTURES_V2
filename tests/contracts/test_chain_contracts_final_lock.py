from __future__ import annotations

from typing import cast

import pytest

from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from core.portfolio.portfolio_engine import PortfolioAllocation
from core.risk.risk_engine import RiskEngine
from domain.enums import Decision, PositionSide, Side, SignalStrength, TriggerLifecycle
from domain.execution import ExecutionOrder
from domain.risk import RiskDecision
from domain.signal import SignalDecision
from domain.trigger import TriggerResult


def make_signal() -> SignalDecision:
    return SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="contract",
        signal_id="s1",
        strategy_name="contract_strategy",
        symbol="au",
        instrument_id="au",
        trade_instrument_id="au_main",
        runtime_id="contract_runtime",
        ts=1,
        bar_ts=1,
        bar_time="1970-01-01T00:00:01Z",
        position_side=PositionSide.LONG,
    )


def make_trigger() -> TriggerResult:
    return TriggerResult(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        lifecycle=TriggerLifecycle.TRIGGERED,
        triggered=True,
        runtime_id="contract_runtime",
        signal_id="s1",
        strategy_name="contract_strategy",
        symbol="au",
        instrument_id="au",
        trade_instrument_id="au_main",
        ts=1,
        bar_ts=1,
        bar_time="1970-01-01T00:00:01Z",
        position_side=PositionSide.LONG,
        confidence=1.0,
        strength=SignalStrength.STRONG,
        reason="contract",
    )


def test_risk_engine_only_accepts_portfolio_allocation() -> None:
    trigger = make_trigger()

    with pytest.raises(AttributeError):
        RiskEngine().evaluate(cast(PortfolioAllocation, trigger))


def test_runtime_main_chain_uses_portfolio_before_risk() -> None:
    runtime = Runtime(RuntimeConfig(runtime_id="contract_runtime", default_quantity=3.0))
    signal = make_signal()

    trigger = runtime.trigger.process(signal, runtime_id=runtime.config.runtime_id)
    allocation = runtime.portfolio.allocate(
        trigger,
        default_quantity=runtime.config.default_quantity,
    )
    risk = runtime.risk.evaluate(allocation)

    assert isinstance(allocation, PortfolioAllocation)
    assert allocation.trigger is trigger
    assert allocation.quantity == 3.0

    assert isinstance(risk, RiskDecision)
    assert risk.quantity == 3.0
    assert risk.instrument_id == "au"
    assert risk.trade_instrument_id == "au_main"


def test_runtime_full_chain_produces_order_through_locked_types() -> None:
    runtime = Runtime(RuntimeConfig(runtime_id="contract_runtime", default_quantity=2.0))
    signal = make_signal()

    trigger = runtime.trigger.process(signal, runtime_id=runtime.config.runtime_id)
    allocation = runtime.portfolio.allocate(
        trigger,
        default_quantity=runtime.config.default_quantity,
    )
    risk = runtime.risk.evaluate(allocation)
    order, result = runtime.execution.execute(risk)

    assert isinstance(allocation, PortfolioAllocation)
    assert isinstance(risk, RiskDecision)
    assert isinstance(order, ExecutionOrder)

    assert result.success is True
    assert order.quantity == 2.0
    assert order.instrument_id == risk.instrument_id
    assert order.trade_instrument_id == risk.trade_instrument_id


def test_execution_result_ts_contract_is_explicit() -> None:
    runtime = Runtime(RuntimeConfig(runtime_id="contract_runtime", default_quantity=1.0))
    signal = make_signal()

    trigger = runtime.trigger.process(signal, runtime_id=runtime.config.runtime_id)
    allocation = runtime.portfolio.allocate(
        trigger,
        default_quantity=runtime.config.default_quantity,
    )
    risk = runtime.risk.evaluate(allocation)
    order, result = runtime.execution.execute(risk)

    assert order is not None
    assert result.success is True
    assert result.ts is not None
