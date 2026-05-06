from __future__ import annotations

from adapters.broker.base import BrokerAdapter
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from core.execution.execution_engine import ExecutionEngine
from core.execution.execution_request import ExecutionRequest
from domain.enums import Decision, ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult
from domain.risk import RiskDecision


class RecordingBroker(BrokerAdapter):
    def __init__(self) -> None:
        self.orders: list[ExecutionOrder] = []

    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        self.orders.append(order)
        return ExecutionResult(
            success=True,
            status=ExecutionStatus.SUBMITTED,
            order_id=f"order-{len(self.orders)}",
            ts=1,
        )


class QuoteStub(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=100.0, volume=1000.0, ts=1)


def _risk_decision(quantity: float | None) -> RiskDecision:
    return RiskDecision(
        instrument_id="au",
        trade_instrument_id="SHFE.au2606",
        allowed=True,
        decision=Decision.OPEN_LONG,
        side=Side.BUY,
        position_side=PositionSide.LONG,
        lifecycle=None,
        quantity=quantity,
        reason="authorized",
    )


def test_execution_engine_uses_risk_decision_quantity_for_order() -> None:
    broker = RecordingBroker()
    decision = _risk_decision(2.5)

    order, _result = ExecutionEngine(broker).execute_request(
        ExecutionRequest(risk_decision=decision, order_price=450.0)
    )

    assert order is not None
    assert order.quantity == 2.5
    assert broker.orders[0].quantity == 2.5


def test_execution_request_handoff_does_not_modify_risk_decision_quantity() -> None:
    broker = RecordingBroker()
    decision = _risk_decision(4.0)
    request = ExecutionRequest(risk_decision=decision, order_price=451.0)

    order, _result = ExecutionEngine(broker).execute_request(request)

    assert decision.quantity == 4.0
    assert request.risk_decision.quantity == 4.0
    assert order is not None
    assert order.quantity == 4.0


def test_missing_or_invalid_quantity_does_not_submit() -> None:
    for quantity in (None, 0.0, -1.0):
        broker = RecordingBroker()

        order, result = ExecutionEngine(broker).execute(_risk_decision(quantity))

        assert order is None
        assert result.status == ExecutionStatus.REJECTED
        assert broker.orders == []


def test_execution_engine_does_not_override_quantity_from_external_position() -> None:
    broker = RecordingBroker()
    decision = _risk_decision(1.0)

    order, _result = ExecutionEngine(broker).execute_request(
        ExecutionRequest(risk_decision=decision, order_price=452.0)
    )

    assert order is not None
    assert order.quantity == 1.0
    assert broker.orders[0].quantity == 1.0


def test_close_path_quantity_comes_from_authorized_risk_decision() -> None:
    runtime = Runtime(
        RuntimeConfig(),
        market_data=QuoteStub(),
        broker=RecordingBroker(),
        runtime_id="rt_quantity_contract",
        scope="local",
    )
    runtime.record_broker_result(
        ExecutionOrder(
            instrument_id="au",
            trade_instrument_id="SHFE.au2606",
            side=Side.BUY,
            position_side=PositionSide.LONG,
            quantity=2.0,
            order_type="limit",
            price=100.0,
        ),
        ExecutionResult(
            success=True,
            status=ExecutionStatus.FILLED,
            order_id="open-1",
            ts=1,
            fill_price=100.0,
            filled_quantity=2.0,
            remaining_quantity=0.0,
            avg_fill_price=100.0,
        ),
        strategy_name="entry",
        symbol="au",
    )
    position = next(iter(runtime.state.portfolio.positions.values()))
    risk_decision = runtime.risk.authorize_close_position(
        position=position,
        side=Side.SELL,
        reason="contract_close",
    )

    assert risk_decision.quantity == 2.0

    executed = runtime.execute_close_position(
        position=position,
        current_price=99.0,
        strategy_name="exit",
        strategy_impl="ExitService",
        symbol="au",
        reason="contract_close",
    )

    broker = runtime.execution.broker
    assert isinstance(broker, RecordingBroker)
    assert executed is True
    assert broker.orders[-1].quantity == risk_decision.quantity
