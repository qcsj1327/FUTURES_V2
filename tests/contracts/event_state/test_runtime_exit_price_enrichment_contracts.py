from __future__ import annotations

from adapters.broker.base import BrokerAdapter
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from app.universe_runtime import UniverseRuntime
from core.services.marketdata.types import MarketBar
from core.signal_router.router import RouterConfig
from domain.enums import Decision, ExecutionStatus, PositionSide, Side, SignalStrength
from domain.execution import ExecutionOrder, ExecutionResult
from domain.signal import SignalDecision
from strategies.base.strategy import Strategy
from strategies.strategy_set import StrategyEntry, StrategySet


class QuoteStub(MarketDataAdapter):
    def __init__(self) -> None:
        self.price = 100.0

    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=self.price, volume=1000.0, ts=1)


class VolatileQuoteStub(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(
            symbol=symbol,
            price=100.0,
            volume=1000.0,
            ts=1,
            bars={
                "5m": MarketBar(
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1000.0,
                    ts=1,
                )
            },
        )


class BrokerStub(BrokerAdapter):
    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        return ExecutionResult(
            success=True,
            status=ExecutionStatus.SUBMITTED,
            order_id="stub",
            ts=1,
        )


class FillBroker(BrokerAdapter):
    def __init__(self) -> None:
        self.orders: list[ExecutionOrder] = []

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        self.orders.append(order)
        return ExecutionResult(
            success=True,
            status=ExecutionStatus.FILLED,
            order_id=f"fill-{len(self.orders)}",
            ts=len(self.orders),
            fill_price=order.price,
            filled_quantity=order.quantity,
            remaining_quantity=0.0,
            avg_fill_price=order.price,
        )


class MultiQuoteStub(MarketDataAdapter):
    def __init__(self, prices: dict[str, float]) -> None:
        self.prices = dict(prices)

    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(
            symbol=symbol,
            price=self.prices[symbol],
            volume=1000.0,
            ts=1,
        )


class RankStrategy(Strategy):
    def generate(self, symbol: str, quote: MarketQuote) -> SignalDecision:
        if symbol == "rb":
            return SignalDecision(
                decision=Decision.OPEN_LONG,
                side=Side.BUY,
                strength=SignalStrength.STRONG,
                confidence=1.0,
                reason="rank rb",
                symbol=symbol,
            )
        return SignalDecision(
            decision=Decision.HOLD,
            side=Side.BUY,
            strength=SignalStrength.WEAK,
            confidence=0.0,
            reason="hold",
            symbol=symbol,
        )


def test_runtime_enriches_open_decision_with_absolute_stop_loss_take_profit() -> None:
    runtime = Runtime(
        RuntimeConfig(stop_loss_pct=0.01, take_profit_pct=0.02),
        market_data=QuoteStub(),
        broker=BrokerStub(),
        runtime_id="rt_contract",
        scope="local",
    )

    decision = SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.MEDIUM,
        confidence=1.0,
        reason="contract",
        symbol="au",
    )
    enriched = runtime._inject_instrument(decision, base_symbol="au", ts=1)

    assert enriched.stop_loss == 99.0
    assert enriched.take_profit == 102.0


def test_runtime_enriches_open_decision_with_dynamic_exit_thresholds() -> None:
    runtime = Runtime(
        RuntimeConfig(
            dynamic_exit_enabled=True,
            dynamic_stop_loss_vol_mult=2.0,
            dynamic_take_profit_vol_mult=3.0,
            dynamic_min_stop_loss_pct=0.005,
            dynamic_min_take_profit_pct=0.01,
            dynamic_max_stop_loss_pct=0.05,
            dynamic_max_take_profit_pct=0.08,
        ),
        market_data=VolatileQuoteStub(),
        broker=BrokerStub(),
        runtime_id="rt_contract",
        scope="local",
    )

    decision = SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.MEDIUM,
        confidence=1.0,
        reason="contract",
        symbol="au",
    )
    enriched = runtime._inject_instrument(decision, base_symbol="au", ts=1)

    assert enriched.stop_loss == 96.0
    assert enriched.take_profit == 106.0


def test_runtime_uses_stored_exit_prices_to_create_close_order() -> None:
    quotes = QuoteStub()
    runtime = Runtime(
        RuntimeConfig(stop_loss_pct=0.01, take_profit_pct=0.02),
        market_data=quotes,
        broker=BrokerStub(),
        runtime_id="rt_contract",
        scope="local",
    )

    open_order = ExecutionOrder(
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        side=Side.BUY,
        position_side=PositionSide.LONG,
        quantity=1.0,
        order_type="limit",
        price=100.0,
        stop_loss=99.0,
        take_profit=102.0,
    )
    runtime.record_broker_result(
        open_order,
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

    position = next(iter(runtime.state.portfolio.positions.values()))
    close_order = runtime.create_exit_order_for_position(
        position=position,
        current_price=103.0,
    )

    assert close_order is not None
    assert close_order.side == Side.SELL
    assert close_order.price == 103.0
    assert close_order.stop_loss == 99.0
    assert close_order.take_profit == 102.0


def test_runtime_portfolio_metrics_are_observation_not_state_mutation() -> None:
    quotes = QuoteStub()
    runtime = Runtime(
        RuntimeConfig(),
        market_data=quotes,
        broker=BrokerStub(),
        runtime_id="rt_contract",
        scope="local",
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

    quotes.price = 101.0
    runtime._refresh_portfolio_metrics()
    position = next(iter(runtime.state.portfolio.positions.values()))

    assert position.unrealized_pnl == 0.0
    assert runtime.state.portfolio.unrealized_pnl == 0.0
    assert runtime._portfolio_metrics_snapshot["source"] == "runtime_observation"
    assert runtime._portfolio_metrics_snapshot["state_source_of_truth"] is False
    assert runtime._portfolio_metrics_snapshot["unrealized_pnl_by_symbol"] == {"au": 1000.0}


def test_universe_runtime_checks_existing_position_exits_outside_active_topn() -> None:
    quotes = MultiQuoteStub({"au": 100.0, "rb": 3500.0})
    broker = FillBroker()
    runtime = Runtime(
        RuntimeConfig(),
        market_data=quotes,
        broker=broker,
        runtime_id="rt_contract",
        scope="local",
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
            stop_loss=99.0,
            take_profit=102.0,
        ),
        ExecutionResult(
            success=True,
            status=ExecutionStatus.FILLED,
            order_id="open-au",
            ts=1,
            fill_price=100.0,
            filled_quantity=1.0,
            remaining_quantity=0.0,
            avg_fill_price=100.0,
        ),
        strategy_name="entry",
        symbol="au",
    )
    quotes.prices["au"] = 103.0

    universe = UniverseRuntime(
        executor=runtime,
        market_data=quotes,
        universe_symbols=["au", "rb"],
        strategy_set=StrategySet(
            [
                StrategyEntry(
                    name="rank_strategy",
                    strategy=RankStrategy(),
                    symbols=["au", "rb"],
                    priority=1,
                    params={},
                )
            ]
        ),
        strategy_priorities={"rank_strategy": 1},
        strategy_weights={"rank_strategy": 1.0},
        router_config=RouterConfig(),
        active_top_n=1,
        enabled_strategies_by_symbol={"au": ["rank_strategy"], "rb": ["rank_strategy"]},
    )
    universe.run_tick()

    assert any(order.instrument_id == "au" and order.side == Side.SELL for order in broker.orders)
