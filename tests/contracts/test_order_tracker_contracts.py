from __future__ import annotations

import pytest

from adapters.broker.order.order_tracker import OrderTracker
from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from domain.enums import OrderStatus, PositionSide, Side
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


def test_order_tracker_records_created_submitted_filled_lifecycle() -> None:
    tracker = OrderTracker()
    order = make_order(quantity=10.0)

    tracker.create(order_id="o1", order=order)
    tracker.submit("o1")
    record = tracker.fill(
        order_id="o1",
        filled_quantity=10.0,
        remaining_quantity=0.0,
    )

    assert record.status == OrderStatus.FILLED
    assert record.filled_quantity == 10.0
    assert record.remaining_quantity == 0.0
    assert tracker.status_history("o1") == [
        OrderStatus.CREATED,
        OrderStatus.SUBMITTED,
        OrderStatus.FILLED,
    ]


def test_order_tracker_records_partial_fill_lifecycle() -> None:
    tracker = OrderTracker()
    order = make_order(quantity=10.0)

    tracker.create(order_id="o1", order=order)
    tracker.submit("o1")
    record = tracker.fill(
        order_id="o1",
        filled_quantity=4.0,
        remaining_quantity=6.0,
    )

    assert record.status == OrderStatus.PARTIALLY_FILLED
    assert record.filled_quantity == 4.0
    assert record.remaining_quantity == 6.0


def test_order_tracker_records_rejected_lifecycle() -> None:
    tracker = OrderTracker()
    order = make_order(quantity=10.0)

    tracker.create(order_id="o1", order=order)
    tracker.submit("o1")
    record = tracker.reject(order_id="o1", reason="rejected")

    assert record.status == OrderStatus.REJECTED
    assert record.filled_quantity == 0.0
    assert record.remaining_quantity == 10.0
    assert record.reason == "rejected"
    assert tracker.status_history("o1") == [
        OrderStatus.CREATED,
        OrderStatus.SUBMITTED,
        OrderStatus.REJECTED,
    ]


def test_order_tracker_rejects_duplicate_order_id() -> None:
    tracker = OrderTracker()
    order = make_order()

    tracker.create(order_id="o1", order=order)

    with pytest.raises(ValueError, match="duplicate_order_id"):
        tracker.create(order_id="o1", order=order)


def test_order_tracker_rejects_missing_order_record() -> None:
    tracker = OrderTracker()

    with pytest.raises(ValueError, match="missing_order_record"):
        tracker.submit("missing")


def test_order_tracker_rejects_invalid_fill_quantities() -> None:
    tracker = OrderTracker()
    tracker.create(order_id="o1", order=make_order(quantity=10.0))
    tracker.submit("o1")

    with pytest.raises(ValueError, match="fill_quantities_do_not_match_order_quantity"):
        tracker.fill(
            order_id="o1",
            filled_quantity=4.0,
            remaining_quantity=5.0,
        )


def test_simulated_broker_records_full_fill_order_lifecycle() -> None:
    broker = SimulatedBroker(SimulatedMarketData(), fill_ratio=1.0)

    result = broker.submit_order(make_order(quantity=10.0))

    assert result.order_id is not None
    assert broker.order_tracker.status_history(result.order_id) == [
        OrderStatus.CREATED,
        OrderStatus.SUBMITTED,
        OrderStatus.FILLED,
    ]


def test_simulated_broker_records_partial_fill_order_lifecycle() -> None:
    broker = SimulatedBroker(SimulatedMarketData(), fill_ratio=0.4)

    result = broker.submit_order(make_order(quantity=10.0))

    assert result.order_id is not None
    record = broker.order_tracker.get(result.order_id)

    assert record.status == OrderStatus.PARTIALLY_FILLED
    assert record.filled_quantity == 4.0
    assert record.remaining_quantity == 6.0


def test_simulated_broker_records_rejected_order_lifecycle() -> None:
    broker = SimulatedBroker(
        SimulatedMarketData(),
        reject_next_order=True,
    )

    result = broker.submit_order(make_order(quantity=10.0))

    assert result.order_id is not None
    assert broker.order_tracker.status_history(result.order_id) == [
        OrderStatus.CREATED,
        OrderStatus.SUBMITTED,
        OrderStatus.REJECTED,
    ]
