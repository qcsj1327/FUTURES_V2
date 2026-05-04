from __future__ import annotations

from dataclasses import dataclass

from adapters.broker.tqkq_live_broker import TqKqLiveBroker
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from core.execution.lifecycle_reasons import TQKQ_LIVE_FILL, TQKQ_LIVE_PARTIAL_FILL
from core.instruments.resolver import InstrumentResolver
from core.instruments.roll_policy import RollPolicy
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


class _FakeMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=120.0, volume=1000.0, ts=1)


@dataclass
class _NativeOrder:
    status: str = "SUBMITTED"
    filled_quantity: float = 0.0
    remaining_quantity: float = 1.0
    avg_fill_price: float | None = None


class _FakeApi:
    def __init__(self) -> None:
        self.order = _NativeOrder()
        self.poll_count = 0

    def insert_order(self, **_kwargs: object) -> _NativeOrder:
        return self.order

    def wait_update(self, deadline: float | None = None) -> bool:
        _ = deadline
        self.poll_count += 1
        if self.poll_count == 1:
            self.order.status = "PARTIAL"
            self.order.filled_quantity = 0.4
            self.order.remaining_quantity = 0.6
            self.order.avg_fill_price = 120.0
        else:
            self.order.status = "FILLED"
            self.order.filled_quantity = 1.0
            self.order.remaining_quantity = 0.0
            self.order.avg_fill_price = 120.0
        return True


def test_tqkq_live_broker_status_mapping_lifecycle_cost_contract() -> None:
    store = MemoryDataStore(env="live", runtime_id="rt_tqkq_status")
    market_data = _FakeMarketData()
    broker = TqKqLiveBroker(
        market_data=market_data,
        dry_run=False,
        api_factory=lambda: _FakeApi(),
    )
    runtime = Runtime(
        config=RuntimeConfig(runtime_id="rt_tqkq_status"),
        market_data=market_data,
        broker=broker,
        datastore=store,
        runtime_id="rt_tqkq_status",
        instrument_resolver=InstrumentResolver(
            roll_policy=RollPolicy(
                mode="fixed_contract",
                contracts={"au": "SHFE.au2406"},
                runtime_id="rt_tqkq_status",
                env="live",
                sink=store,
            )
        ),
    )
    runtime.run(
        SignalDecision(
            decision=Decision.OPEN_LONG,
            side=Side.BUY,
            strength=SignalStrength.STRONG,
            confidence=1.0,
            reason="contract",
            symbol="au",
            instrument_id="au",
            trade_instrument_id="SHFE.au2406",
            position_side=PositionSide.LONG,
            ts=1,
        ),
        strategy_name="contract",
        strategy_impl="contract",
        market_ts=1,
    )
    runtime.poll_order_lifecycle(1)
    runtime.poll_order_lifecycle(2)

    statuses = [event["status"] for event in store.order_lifecycle_events]
    assert statuses == ["NEW", "SUBMITTED", "PARTIAL", "FILLED"]
    partial = store.order_lifecycle_events[2]
    filled = store.order_lifecycle_events[3]
    assert partial["reason"] == TQKQ_LIVE_PARTIAL_FILL
    assert partial["filled_quantity"] == 0.4
    assert partial["remaining_quantity"] == 0.6
    assert filled["reason"] == TQKQ_LIVE_FILL
    cost_fields = {
        "market_price",
        "raw_fill_price",
        "fill_price",
        "multiplier",
        "tick_size",
        "notional",
        "commission",
        "slippage",
        "cost_total",
        "margin",
    }
    for event in (partial, filled):
        assert cost_fields.issubset(event.keys())
        assert event["market_price"] == 120.0
        assert event["raw_fill_price"] == 120.0
        assert event["fill_price"] == 120.0
        assert event["notional"] > 0
        assert event["cost_total"] >= 0
    for event in store.order_lifecycle_events:
        assert event["order_id"]
        assert event["instrument_id"] == "au"
        assert event["trade_instrument_id"] == "SHFE.au2406"
        assert "avg_fill_price" in event
