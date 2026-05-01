from __future__ import annotations

import pytest

from adapters.broker.order.order_id_generator import OrderIdGenerator
from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from domain.enums import PositionSide, Side
from domain.execution import ExecutionOrder


def make_order() -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au_main",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=1.0,
        order_type="market",
    )


def test_order_id_generator_is_sequential() -> None:
    generator = OrderIdGenerator(prefix="test_order")

    assert generator.next_id() == "test_order_1"
    assert generator.next_id() == "test_order_2"
    assert generator.next_id() == "test_order_3"


def test_order_id_generator_requires_prefix() -> None:
    with pytest.raises(ValueError, match="order_id_prefix_required"):
        OrderIdGenerator(prefix="")


def test_simulated_broker_uses_order_id_generator() -> None:
    broker = SimulatedBroker(
        SimulatedMarketData(),
        order_id_prefix="broker_order",
    )

    first = broker.submit_order(make_order())
    second = broker.submit_order(make_order())

    assert first.order_id == "broker_order_1"
    assert second.order_id == "broker_order_2"


def test_simulated_broker_keeps_default_order_id_prefix() -> None:
    broker = SimulatedBroker(SimulatedMarketData())

    result = broker.submit_order(make_order())

    assert result.order_id == "sim_order_1"
