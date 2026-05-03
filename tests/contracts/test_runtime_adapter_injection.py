from __future__ import annotations

import pytest

from adapters.broker.base import BrokerAdapter
from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from domain.enums import ExecutionStatus
from domain.execution import ExecutionOrder, ExecutionResult


class FixedMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=101.0, volume=1000.0, ts=1)


class RecordingBroker(BrokerAdapter):
    def __init__(self) -> None:
        self.orders: list[ExecutionOrder] = []

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        self.orders.append(order)
        return ExecutionResult(
            success=True,
            status=ExecutionStatus.FILLED,
            order_id="recorded_1",
            ts=1,
            fill_price=101.0,
            filled_quantity=order.quantity,
            remaining_quantity=0.0,
            avg_fill_price=101.0,
            reason="recorded_fill",
        )


def test_runtime_requires_explicit_adapters() -> None:
    with pytest.raises(TypeError):
        Runtime()  # type: ignore[call-arg]


def test_runtime_accepts_injected_market_data_and_broker() -> None:
    market_data = FixedMarketData()
    broker = RecordingBroker()

    runtime = Runtime(
        RuntimeConfig(symbol="au", default_quantity=1.0),
        market_data=market_data,
        broker=broker,
    )

    runtime.run_market_once()

    assert runtime.market_data is market_data
    assert runtime.execution.broker is broker
    assert broker.orders
    assert runtime.orders_submitted == 1


def test_runtime_factory_builds_simulated_runtime() -> None:
    runtime = RuntimeFactory.build_simulated_runtime(
        RuntimeConfig(symbol="au", default_quantity=1.0)
    )

    assert isinstance(runtime.market_data, SimulatedMarketData)
    assert isinstance(runtime.execution.broker, SimulatedBroker)
