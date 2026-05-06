from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from adapters.broker.base import BrokerAdapter
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult


class QuoteStub(MarketDataAdapter):
    def __init__(self, price: float = 100.0) -> None:
        self.price = price

    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=self.price, volume=1000.0, ts=1)


class PortfolioSyncBroker(BrokerAdapter):
    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            status=ExecutionStatus.FILLED,
            order_id="fill-1",
            ts=1,
            fill_price=order.price,
            filled_quantity=order.quantity,
            remaining_quantity=0.0,
            avg_fill_price=order.price,
        )

    def portfolio_snapshot(self) -> dict[str, object]:
        return {
            "cash": 123456.0,
            "equity": 234567.0,
            "margin_used": 3456.0,
            "positions": {
                "au": {
                    "quantity": 99.0,
                    "avg_price": 1.0,
                }
            },
        }


def _runtime_with_position() -> Runtime:
    runtime = Runtime(
        RuntimeConfig(),
        market_data=QuoteStub(price=100.0),
        broker=PortfolioSyncBroker(),
        runtime_id="rt_authority",
        scope="live",
    )
    runtime.record_broker_result(
        ExecutionOrder(
            instrument_id="au",
            trade_instrument_id="SHFE.au2606",
            side=Side.BUY,
            position_side=PositionSide.LONG,
            quantity=1.0,
            order_type="limit",
            price=100.0,
        ),
        ExecutionResult(
            success=True,
            status=ExecutionStatus.FILLED,
            order_id="open-1",
            ts=1,
            fill_price=100.0,
            filled_quantity=1.0,
            remaining_quantity=0.0,
            avg_fill_price=100.0,
        ),
        strategy_name="entry",
        symbol="au",
    )
    return runtime


def test_refresh_portfolio_metrics_does_not_replace_portfolio_object() -> None:
    runtime = _runtime_with_position()
    portfolio_before = runtime.state.portfolio

    runtime._refresh_portfolio_metrics()

    assert runtime.state.portfolio is portfolio_before


def test_refresh_portfolio_metrics_does_not_mutate_true_positions() -> None:
    runtime = _runtime_with_position()
    portfolio_before = runtime.state.portfolio
    positions_before = dict(portfolio_before.positions)

    quote_source = runtime.market_data
    assert isinstance(quote_source, QuoteStub)
    quote_source.price = 110.0
    runtime._refresh_portfolio_metrics()

    assert runtime.state.portfolio.positions == positions_before
    position = next(iter(runtime.state.portfolio.positions.values()))
    assert position.quantity == 1.0
    assert position.avg_price == 100.0
    assert position.unrealized_pnl == 0.0


def test_broker_portfolio_sync_is_observation_not_state_source() -> None:
    runtime = _runtime_with_position()

    runtime._refresh_portfolio_metrics()

    assert runtime.state.portfolio.cash is None
    assert runtime.state.portfolio.equity is None
    assert runtime.state.portfolio.positions
    assert runtime.state.portfolio.metadata == {}
    assert runtime._last_portfolio_sync["cash"] == 123456.0
    sync = cast(
        Mapping[str, object],
        runtime._portfolio_metrics_snapshot["broker_portfolio_sync_observation"],
    )
    assert sync["cash"] == 123456.0
    assert runtime._portfolio_metrics_snapshot["state_source_of_truth"] is False
