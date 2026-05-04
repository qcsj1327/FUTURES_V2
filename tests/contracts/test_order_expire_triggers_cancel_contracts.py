from __future__ import annotations

from adapters.broker.tqkq_live_broker import TqKqLiveBroker
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from core.execution.lifecycle_reasons import EXPIRED
from core.instruments.resolver import InstrumentResolver
from core.instruments.roll_policy import RollPolicy
from domain.enums import Decision, PositionSide, Side, SignalStrength
from domain.signal import SignalDecision


class _FakeMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=120.0, volume=1000.0, ts=1)


def test_expire_triggers_cancel_contract() -> None:
    store = MemoryDataStore(env="live", runtime_id="rt_expire_cancel")
    market_data = _FakeMarketData()
    broker = TqKqLiveBroker(market_data=market_data, dry_run=True)
    runtime = Runtime(
        config=RuntimeConfig(runtime_id="rt_expire_cancel"),
        market_data=market_data,
        broker=broker,
        datastore=store,
        runtime_id="rt_expire_cancel",
        instrument_resolver=InstrumentResolver(
            roll_policy=RollPolicy(
                mode="fixed_contract",
                contracts={"au": "SHFE.au2406"},
                runtime_id="rt_expire_cancel",
                env="live",
                sink=store,
            )
        ),
    )
    runtime.max_pending_ticks = 1
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

    expired = [event for event in store.order_lifecycle_events if event["status"] == "EXPIRED"]
    assert expired
    assert expired[0]["reason"] == EXPIRED
    assert broker.cancel_calls == [("tqkq_live_order_1", EXPIRED)]
