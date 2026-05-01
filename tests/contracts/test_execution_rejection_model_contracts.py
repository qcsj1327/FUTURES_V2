from __future__ import annotations

import pytest

from adapters.broker.order.rejection_policy import RejectionPolicy
from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from core.execution.execution_engine import ExecutionEngine
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder


def make_order(
    *,
    instrument_id: str = "au",
    trade_instrument_id: str = "au_main",
    side: Side = Side.BUY,
    quantity: float = 1.0,
) -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id=instrument_id,
        trade_instrument_id=trade_instrument_id,
        side=side,
        position_side=PositionSide.LONG if side == Side.BUY else PositionSide.SHORT,
        quantity=quantity,
        order_type="market",
    )


def test_rejection_policy_rejects_negative_quantity_limit() -> None:
    with pytest.raises(
        ValueError,
        match="reject_above_quantity_must_be_non_negative",
    ):
        RejectionPolicy(reject_above_quantity=-1.0)


def test_simulated_broker_can_reject_next_order_once() -> None:
    broker = SimulatedBroker(
        SimulatedMarketData(),
        reject_next_order=True,
    )

    first = broker.submit_order(make_order())
    second = broker.submit_order(make_order())

    assert first.success is False
    assert first.status == ExecutionStatus.REJECTED
    assert first.order_id == "sim_order_1"
    assert first.ts is not None
    assert first.fill_price is None
    assert first.reason == "reject_next_order"

    assert second.success is True
    assert second.status == ExecutionStatus.FILLED
    assert second.order_id == "sim_order_2"
    assert second.fill_price is not None


def test_simulated_broker_rejects_by_instrument_id() -> None:
    broker = SimulatedBroker(
        SimulatedMarketData(),
        rejected_symbols={"au"},
    )

    result = broker.submit_order(
        make_order(
            instrument_id="au",
            trade_instrument_id="au_main",
        )
    )

    assert result.success is False
    assert result.status == ExecutionStatus.REJECTED
    assert result.reason == "rejected_symbol"


def test_simulated_broker_rejects_by_trade_instrument_id() -> None:
    broker = SimulatedBroker(
        SimulatedMarketData(),
        rejected_symbols={"au_main"},
    )

    result = broker.submit_order(
        make_order(
            instrument_id="au",
            trade_instrument_id="au_main",
        )
    )

    assert result.success is False
    assert result.status == ExecutionStatus.REJECTED
    assert result.reason == "rejected_symbol"


def test_simulated_broker_rejects_above_quantity() -> None:
    broker = SimulatedBroker(
        SimulatedMarketData(),
        reject_above_quantity=2.0,
    )

    result = broker.submit_order(make_order(quantity=3.0))

    assert result.success is False
    assert result.status == ExecutionStatus.REJECTED
    assert result.reason == "quantity_rejected"


def test_simulated_broker_allows_quantity_at_limit() -> None:
    broker = SimulatedBroker(
        SimulatedMarketData(),
        reject_above_quantity=2.0,
    )

    result = broker.submit_order(make_order(quantity=2.0))

    assert result.success is True
    assert result.status == ExecutionStatus.FILLED
    assert result.fill_price is not None


def test_market_loop_broker_rejection_does_not_update_position() -> None:
    runtime = Runtime(RuntimeConfig(symbol="au", default_quantity=1.0))
    runtime.execution = ExecutionEngine(
        SimulatedBroker(
            runtime.market_data,
            reject_next_order=True,
        )
    )

    runtime.run_market_once()

    assert runtime.orders_submitted == 0
    assert runtime.state.portfolio.positions == {}
