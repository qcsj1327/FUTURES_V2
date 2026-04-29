from __future__ import annotations

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from domain.enums import PositionSide, Side
from domain.execution import ExecutionOrder


def test_simulated_broker_uses_market_price() -> None:
    market = SimulatedMarketData()
    broker = SimulatedBroker(market)

    order = ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au_main",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=1.0,
        order_type="market",
    )

    result = broker.submit_order(order)

    assert result.success is True
    assert result.order_id == "sim_order_1"
    assert result.fill_price is not None
    assert result.fill_price > 0
    assert result.reason == "simulated_fill"
