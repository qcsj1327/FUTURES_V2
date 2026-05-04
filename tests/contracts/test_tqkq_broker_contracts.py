from __future__ import annotations

from adapters.broker.tqkq_broker import TqKqBroker
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from core.instruments.resolver import InstrumentResolver
from core.instruments.roll_policy import RollPolicy
from core.instruments.specs import InstrumentSpecRegistry
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


class _FakeMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=450.0, volume=1000.0, ts=1)


class _FakeApi:
    pass


def test_tqkq_broker_emits_lifecycle_and_cost_fields_through_runtime() -> None:
    runtime_id = "rt_tqkq_broker"
    store = MemoryDataStore(env="live", runtime_id=runtime_id)
    market_data = _FakeMarketData()
    broker = TqKqBroker(
        market_data=market_data,
        instrument_specs=InstrumentSpecRegistry(),
        api_factory=lambda: _FakeApi(),
    )
    resolver = InstrumentResolver(
        roll_policy=RollPolicy(
            mode="fixed_contract",
            contracts={"au": "SHFE.au2406"},
            runtime_id=runtime_id,
            env="live",
            sink=store,
        )
    )
    runtime = RuntimeFactory.build_live_runtime(
        config=RuntimeConfig(runtime_id=runtime_id, default_quantity=1.0),
        runtime_id=runtime_id,
        market_data=market_data,
        broker=broker,
        datastore=store,
        instrument_resolver=resolver,
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
            position_side=PositionSide.LONG,
            ts=1,
        ),
        strategy_name="contract",
        strategy_impl="contract",
        market_ts=1,
    )

    assert store.order_events
    assert store.order_lifecycle_events
    order_event = store.order_events[0]
    lifecycle_event = store.order_lifecycle_events[0]
    assert order_event["trade_instrument_id"] == "SHFE.au2406"
    assert not order_event["trade_instrument_id"].endswith("_main")
    assert lifecycle_event["trade_instrument_id"] == "SHFE.au2406"
    for key in ("notional", "commission", "slippage", "cost_total", "margin"):
        assert key in lifecycle_event

