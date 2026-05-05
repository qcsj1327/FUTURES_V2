from __future__ import annotations

from adapters.broker.tqkq_live_broker import TqKqLiveBroker
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from core.execution.lifecycle_reasons import (
    INVALID_TRADE_INSTRUMENT_ID_MAIN_ALIAS,
    INVALID_TRADE_INSTRUMENT_ID_NOT_REAL_CONTRACT,
    MISSING_TRADE_INSTRUMENT_ID,
)
from domain.enums import PositionSide, Side
from domain.execution import ExecutionOrder


class _FakeMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=120.0, volume=1000.0, ts=1)


def _order(trade_id: str | None) -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id="au",
        trade_instrument_id=trade_id,
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=1.0,
        order_type="market",
    )


def test_tqkq_live_broker_rejects_invalid_trade_id_contracts() -> None:
    store = MemoryDataStore(env="live", runtime_id="rt_invalid_tqkq_live")
    market_data = _FakeMarketData()
    broker = TqKqLiveBroker(market_data=market_data)
    runtime = Runtime(
        config=RuntimeConfig(runtime_id="rt_invalid_tqkq_live"),
        market_data=market_data,
        broker=broker,
        datastore=store,
        runtime_id="rt_invalid_tqkq_live",
    )

    for trade_id in (None, "au_main", "au2406", "SHFE.au"):
        order = _order(trade_id)
        result = broker.submit_order(order)
        runtime.record_broker_result(
            order,
            result,
            strategy_name="contract",
            strategy_impl="contract",
            symbol="au",
        )

    rejected = [event for event in store.order_lifecycle_events if event["status"] == "REJECTED"]
    reasons = {event["reason"] for event in rejected}
    assert MISSING_TRADE_INSTRUMENT_ID in reasons
    assert INVALID_TRADE_INSTRUMENT_ID_MAIN_ALIAS in reasons
    assert INVALID_TRADE_INSTRUMENT_ID_NOT_REAL_CONTRACT in reasons
