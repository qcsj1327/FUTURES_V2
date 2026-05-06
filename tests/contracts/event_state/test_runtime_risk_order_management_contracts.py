from __future__ import annotations

from adapters.broker.base import BrokerAdapter
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime import Runtime
from core.execution.lifecycle_reasons import RISK_MAX_RISK_RATIO, SIMULATED_FILL
from core.risk.portfolio_risk_limits import PortfolioRiskLimits
from core.services.marketdata.types import MarketDataAdapter, MarketQuote
from domain.enums import Decision, ExecutionStatus, PositionSide, Side, SignalStrength
from domain.execution import ExecutionOrder, ExecutionResult
from domain.signal import SignalDecision


class FixedMarketData(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=100.0, volume=1000.0, ts=1)


class RecordingBroker(BrokerAdapter):
    def __init__(self) -> None:
        self.submitted: list[ExecutionOrder] = []

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        self.submitted.append(order)
        return ExecutionResult(
            success=True,
            status=ExecutionStatus.FILLED,
            ts=1,
            order_id=f"recorded_{len(self.submitted)}",
            fill_price=100.0,
            filled_quantity=order.quantity,
            remaining_quantity=0.0,
            avg_fill_price=100.0,
            reason=SIMULATED_FILL,
        )


def _decision() -> SignalDecision:
    return SignalDecision(
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        strength=SignalStrength.STRONG,
        confidence=1.0,
        reason="risk_contract",
        signal_id="sig_risk_contract",
        strategy_name="s1",
        symbol="au",
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        ts=1,
        position_side=PositionSide.LONG,
    )


def test_runtime_portfolio_risk_blocks_before_broker_submit() -> None:
    market = FixedMarketData()
    broker = RecordingBroker()
    store = MemoryDataStore(scope="local", runtime_id="rt_risk_contract")
    runtime = Runtime(
        market_data=market,
        broker=broker,
        datastore=store,
        runtime_id="rt_risk_contract",
        scope="local",
    )
    runtime.initial_equity = 1_000.0
    runtime.portfolio_risk_limits = PortfolioRiskLimits(max_risk_ratio=0.8)

    runtime._run_decision(_decision(), strategy_name="s1", strategy_impl="contract")

    assert broker.submitted == []
    assert store.fill_events == []
    rejects = [
        event
        for event in store.order_lifecycle_events
        if event.get("reason") == RISK_MAX_RISK_RATIO
    ]
    assert rejects
    assert rejects[-1]["status"] == "REJECTED"
    assert rejects[-1]["datastore_scope"] == "local"


def test_runtime_does_not_reopen_symbol_with_active_position() -> None:
    market = FixedMarketData()
    broker = RecordingBroker()
    store = MemoryDataStore(scope="local", runtime_id="rt_order_contract")
    runtime = Runtime(
        market_data=market,
        broker=broker,
        datastore=store,
        runtime_id="rt_order_contract",
        scope="local",
    )

    runtime.run(_decision(), strategy_name="s1", strategy_impl="contract", market_ts=1)
    runtime.run(_decision(), strategy_name="s1", strategy_impl="contract", market_ts=2)

    assert len(broker.submitted) == 1
    assert len(store.fill_events) == 1
    assert [event["status"] for event in store.order_lifecycle_events] == [
        "NEW",
        "FILLED",
    ]
