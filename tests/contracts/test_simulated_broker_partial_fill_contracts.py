from __future__ import annotations

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder


def make_order(quantity: float = 10.0) -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au_main",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=quantity,
        order_type="market",
    )


def test_simulated_broker_full_fill_sets_fill_quantities() -> None:
    broker = SimulatedBroker(SimulatedMarketData(), fill_ratio=1.0)

    result = broker.submit_order(make_order(quantity=10.0))

    assert result.success is True
    assert result.status == ExecutionStatus.FILLED
    assert result.filled_quantity == 10.0
    assert result.remaining_quantity == 0.0
    assert result.avg_fill_price == result.fill_price
    assert result.reason == "simulated_fill"


def test_simulated_broker_partial_fill_sets_partial_quantities() -> None:
    broker = SimulatedBroker(SimulatedMarketData(), fill_ratio=0.4)

    result = broker.submit_order(make_order(quantity=10.0))

    assert result.success is True
    assert result.status == ExecutionStatus.PARTIALLY_FILLED
    assert result.filled_quantity == 4.0
    assert result.remaining_quantity == 6.0
    assert result.avg_fill_price == result.fill_price
    assert result.reason == "simulated_partial_fill"


def test_simulated_broker_rejection_has_no_fill_quantities() -> None:
    broker = SimulatedBroker(
        SimulatedMarketData(),
        reject_next_order=True,
    )

    result = broker.submit_order(make_order(quantity=10.0))

    assert result.success is False
    assert result.status == ExecutionStatus.REJECTED
    assert result.filled_quantity is None
    assert result.remaining_quantity is None
    assert result.avg_fill_price is None
