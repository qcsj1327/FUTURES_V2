from __future__ import annotations

import pytest

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from domain.enums import PositionSide, Side
from domain.execution import ExecutionOrder


def make_order(side: Side) -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au_main",
        side=side,
        position_side=PositionSide.LONG if side == Side.BUY else PositionSide.SHORT,
        quantity=1.0,
        order_type="market",
    )


def test_simulated_broker_buy_slippage_increases_fill_price() -> None:
    market = SimulatedMarketData()
    broker_without_slippage = SimulatedBroker(market, slippage_rate=0.0)
    broker_with_slippage = SimulatedBroker(market, slippage_rate=0.01)

    base = broker_without_slippage.submit_order(make_order(Side.BUY))
    slipped = broker_with_slippage.submit_order(make_order(Side.BUY))

    assert base.fill_price is not None
    assert slipped.fill_price is not None
    assert slipped.fill_price > base.fill_price


def test_simulated_broker_sell_slippage_decreases_fill_price() -> None:
    market = SimulatedMarketData()
    broker_without_slippage = SimulatedBroker(market, slippage_rate=0.0)
    broker_with_slippage = SimulatedBroker(market, slippage_rate=0.01)

    base = broker_without_slippage.submit_order(make_order(Side.SELL))
    slipped = broker_with_slippage.submit_order(make_order(Side.SELL))

    assert base.fill_price is not None
    assert slipped.fill_price is not None
    assert slipped.fill_price < base.fill_price


def test_simulated_broker_rejects_negative_slippage_rate() -> None:
    market = SimulatedMarketData()

    with pytest.raises(ValueError, match="slippage_rate_must_be_non_negative"):
        SimulatedBroker(market, slippage_rate=-0.01)
