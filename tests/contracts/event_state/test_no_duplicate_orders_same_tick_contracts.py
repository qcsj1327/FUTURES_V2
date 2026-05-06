from __future__ import annotations

from adapters.broker.base import BrokerAdapter
from adapters.broker.simulated_broker import SimulatedBroker
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime import Runtime
from core.execution.lifecycle_reasons import DUPLICATE_SAME_TICK
from core.services.marketdata.types import MarketDataAdapter, MarketQuote
from domain.enums import Decision, ExecutionStatus, PositionSide, Side, SignalStrength
from domain.execution import ExecutionOrder, ExecutionResult
from domain.signal import SignalDecision


class CountingBroker(BrokerAdapter):
    def __init__(self) -> None:
        self.submitted: list[ExecutionOrder] = []

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        self.submitted.append(order)
        return ExecutionResult(
            success=True,
            status=ExecutionStatus.FILLED,
            ts=0,
            order_id=f"count_order_{len(self.submitted)}",
            fill_price=100.0,
            reason="simulated_fill",
            filled_quantity=order.quantity,
            remaining_quantity=0.0,
            avg_fill_price=100.0,
        )


class FixedMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=101.0, volume=1000.0, ts=1)


def _order() -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=1.0,
        order_type="market",
    )


def _decision() -> SignalDecision:
    return SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="test",
        signal_id="sig_1",
        strategy_name="s1",
        symbol="au",
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        ts=0,
        position_side=PositionSide.LONG,
    )


def test_runtime_is_duplicate_same_tick_owner_and_blocks_before_broker_submit() -> None:
    market = FixedMarketData()
    broker = CountingBroker()
    store = MemoryDataStore(scope="live", runtime_id="rt_dup_owner")
    runtime = Runtime(
        market_data=market,
        broker=broker,
        datastore=store,
        runtime_id="rt_dup_owner",
        scope="live",
    )

    runtime._run_decision(_decision(), strategy_name="s1", strategy_impl="test")
    runtime._tick = 0
    runtime._run_decision(_decision(), strategy_name="s1", strategy_impl="test")

    assert len(broker.submitted) == 1
    duplicate_events = [
        event
        for event in store.order_lifecycle_events
        if event.get("reason") == DUPLICATE_SAME_TICK
    ]
    assert duplicate_events
    assert duplicate_events[-1]["status"] == "REJECTED"


def test_rejected_order_does_not_reserve_duplicate_same_tick_key() -> None:
    market = FixedMarketData()
    broker = SimulatedBroker(market, reject_next_order=True)
    store = MemoryDataStore(scope="live", runtime_id="rt_dup_reject")
    runtime = Runtime(
        market_data=market,
        broker=broker,
        datastore=store,
        runtime_id="rt_dup_reject",
        scope="live",
    )

    runtime._run_decision(_decision(), strategy_name="s1", strategy_impl="test")
    runtime._tick = 0
    runtime._run_decision(_decision(), strategy_name="s1", strategy_impl="test")

    assert not [
        event
        for event in store.order_lifecycle_events
        if event.get("reason") == DUPLICATE_SAME_TICK
    ]
    assert store.fill_events


def test_no_duplicate_orders_same_tick_writes_rejection_lifecycle() -> None:
    market = FixedMarketData()
    broker = SimulatedBroker(market)
    store = MemoryDataStore(scope="live", runtime_id="rt_dup")
    runtime = Runtime(
        market_data=market,
        broker=broker,
        datastore=store,
        runtime_id="rt_dup",
        scope="live",
    )

    first = _order()
    first_result = broker.submit_order(first)
    runtime.record_broker_result(first, first_result, strategy_name="s1", symbol="au")

    runtime._tick = 0
    second = _order()
    second_result = broker.submit_order(second)
    runtime.record_broker_result(second, second_result, strategy_name="s1", symbol="au")

    duplicate_events = [
        e for e in store.order_lifecycle_events if e.get("reason") == DUPLICATE_SAME_TICK
    ]
    assert duplicate_events
    assert duplicate_events[-1]["status"] == "REJECTED"
    assert duplicate_events[-1]["trade_instrument_id"] == "SHFE.au2606"
