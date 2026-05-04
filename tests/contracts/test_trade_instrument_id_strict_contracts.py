from __future__ import annotations

from adapters.broker.tqkq_live_broker import TqKqLiveBroker
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from core.execution.lifecycle_reasons import (
    INVALID_TRADE_INSTRUMENT_ID_MAIN_ALIAS,
    INVALID_TRADE_INSTRUMENT_ID_NOT_REAL_CONTRACT,
    MISSING_TRADE_INSTRUMENT_ID,
)
from domain.enums import PositionSide, Side
from domain.execution import ExecutionOrder


class _FakeMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=450.0, volume=1000.0, ts=1)


def _order(trade_instrument_id: str | None) -> ExecutionOrder:
    return ExecutionOrder(
        instrument_id="au",
        trade_instrument_id=trade_instrument_id,
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=1.0,
        order_type="market",
    )


def test_exec_scheduler_core_v1_trade_instrument_id_strict_contract() -> None:
    broker = TqKqLiveBroker(market_data=_FakeMarketData())

    missing = broker.submit_order(_order(None))
    main_alias = broker.submit_order(_order("au_main"))
    not_real = broker.submit_order(_order("au2406"))

    assert missing.reason == MISSING_TRADE_INSTRUMENT_ID
    assert main_alias.reason == INVALID_TRADE_INSTRUMENT_ID_MAIN_ALIAS
    assert not_real.reason == INVALID_TRADE_INSTRUMENT_ID_NOT_REAL_CONTRACT
