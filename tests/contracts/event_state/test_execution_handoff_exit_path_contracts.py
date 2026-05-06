from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from adapters.broker.base import BrokerAdapter
from adapters.marketdata.base import MarketDataAdapter, MarketQuote
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from core.execution.execution_request import ExecutionRequest
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult


class QuoteStub(MarketDataAdapter):
    def get_last_quote(self, symbol: str) -> MarketQuote:
        return MarketQuote(symbol=symbol, price=101.0, volume=1000.0, ts=1)


class FailingBroker(BrokerAdapter):
    def submit_order(self, order: ExecutionOrder) -> ExecutionResult:
        raise AssertionError("runtime must not call broker.submit_order directly")


class SpyExecutionEngine:
    def __init__(self) -> None:
        self.broker = FailingBroker()
        self.requests: list[ExecutionRequest] = []
        self.orders: list[ExecutionOrder] = []

    def execute_request(
        self,
        request: ExecutionRequest,
    ) -> tuple[ExecutionOrder | None, ExecutionResult]:
        self.requests.append(request)
        decision = request.risk_decision
        if decision.quantity is None or decision.quantity <= 0 or decision.position_side is None:
            return None, ExecutionResult(
                success=False,
                status=ExecutionStatus.REJECTED,
                reason="invalid_quantity",
            )
        order = ExecutionOrder(
            instrument_id=decision.instrument_id,
            trade_instrument_id=decision.trade_instrument_id,
            side=decision.side,
            position_side=decision.position_side,
            quantity=decision.quantity,
            order_type="market",
            price=request.order_price,
        )
        self.orders.append(order)
        return order, ExecutionResult(
            success=True,
            status=ExecutionStatus.FILLED,
            order_id=f"spy-{len(self.orders)}",
            ts=1,
            fill_price=request.order_price,
            filled_quantity=decision.quantity,
            remaining_quantity=0.0,
            avg_fill_price=request.order_price,
        )


def _runtime_with_position() -> tuple[Runtime, SpyExecutionEngine]:
    runtime = Runtime(
        RuntimeConfig(),
        market_data=QuoteStub(),
        broker=FailingBroker(),
        runtime_id="rt_exit_contract",
        scope="local",
    )
    runtime.record_broker_result(
        ExecutionOrder(
            instrument_id="au",
            trade_instrument_id="SHFE.au2606",
            side=Side.BUY,
            position_side=PositionSide.LONG,
            quantity=3.0,
            order_type="limit",
            price=100.0,
        ),
        ExecutionResult(
            success=True,
            status=ExecutionStatus.FILLED,
            order_id="open-1",
            ts=1,
            fill_price=100.0,
            filled_quantity=3.0,
            remaining_quantity=0.0,
            avg_fill_price=100.0,
        ),
        strategy_name="entry",
        symbol="au",
    )
    spy = SpyExecutionEngine()
    runtime.execution = cast(Any, spy)
    return runtime, spy


def test_runtime_and_universe_runtime_do_not_call_broker_submit_directly() -> None:
    for path in (Path("app/runtime.py"), Path("app/universe_runtime.py")):
        source = path.read_text(encoding="utf-8")
        assert "broker.submit_order" not in source


def test_exit_path_uses_execution_engine_and_translator_state_path() -> None:
    runtime, spy = _runtime_with_position()
    position = next(iter(runtime.state.portfolio.positions.values()))

    executed = runtime.execute_exit_for_position(
        position=position,
        current_price=102.0,
        fallback_take_profit=101.0,
        strategy_name="exit",
        strategy_impl="ExitService",
        symbol="au",
    )

    assert executed is True
    assert len(spy.requests) == 1
    assert spy.requests[0].risk_decision.quantity == 3.0
    assert spy.orders[0].quantity == 3.0
    assert "spy-1" in runtime.state.orders


def test_roll_close_path_uses_execution_engine() -> None:
    runtime, spy = _runtime_with_position()

    closed = runtime._close_roll_positions("au", "SHFE.au2606")

    assert closed is True
    assert len(spy.requests) == 1
    assert spy.requests[0].risk_decision.reason == "roll_close_position"
    assert spy.requests[0].risk_decision.quantity == 3.0
    assert spy.orders[0].quantity == 3.0
