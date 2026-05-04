from __future__ import annotations

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime import Runtime
from domain.enums import PositionSide, Side
from domain.execution import ExecutionOrder


def _order() -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="au_main",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=1.0,
        order_type="market",
    )


def test_no_duplicate_orders_same_tick_writes_rejection_lifecycle() -> None:
    market = SimulatedMarketData()
    broker = SimulatedBroker(market)
    store = MemoryDataStore(env="live", runtime_id="rt_dup")
    runtime = Runtime(
        market_data=market,
        broker=broker,
        datastore=store,
        runtime_id="rt_dup",
        environment="live",
    )

    first = _order()
    first_result = broker.submit_order(first)
    runtime.record_broker_result(first, first_result, strategy_name="s1", symbol="au")

    runtime._tick = 0
    second = _order()
    second_result = broker.submit_order(second)
    runtime.record_broker_result(second, second_result, strategy_name="s1", symbol="au")

    duplicate_events = [
        e
        for e in store.order_lifecycle_events
        if e.get("reason") == "duplicate_order_same_tick"
    ]
    assert duplicate_events
    assert duplicate_events[-1]["status"] == "REJECTED"
    assert duplicate_events[-1]["trade_instrument_id"] == "au_main"
