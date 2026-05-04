from __future__ import annotations

from adapters.broker.tqkq_broker import TqKqBroker
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from core.instruments.specs import InstrumentSpecRegistry
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder


class _FakeMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=450.0, volume=1000.0, ts=1)


def test_tqkq_broker_rejects_missing_trade_instrument_id_without_fallback() -> None:
    broker = TqKqBroker(
        market_data=_FakeMarketData(),
        instrument_specs=InstrumentSpecRegistry(),
    )
    result = broker.submit_order(
        ExecutionOrder(
            instrument_id="au",
            trade_instrument_id=None,
            side=Side.BUY,
            position_side=PositionSide.LONG,
            quantity=1.0,
            order_type="market",
        )
    )

    assert result.status == ExecutionStatus.REJECTED
    assert result.reason == "missing_trade_instrument_id"


def test_tqkq_broker_rejects_main_alias_trade_instrument_id() -> None:
    broker = TqKqBroker(
        market_data=_FakeMarketData(),
        instrument_specs=InstrumentSpecRegistry(),
    )
    result = broker.submit_order(
        ExecutionOrder(
            instrument_id="au",
            trade_instrument_id="au_main",
            side=Side.BUY,
            position_side=PositionSide.LONG,
            quantity=1.0,
            order_type="market",
        )
    )

    assert result.status == ExecutionStatus.REJECTED
    assert result.reason == "invalid_trade_instrument_id_main_alias"

