from __future__ import annotations

from adapters.broker.base import BrokerAdapter
from adapters.marketdata.base import MarketDataAdapter
from app.runtime_config import RuntimeConfig
from core.execution.execution_engine import ExecutionEngine
from core.portfolio.portfolio_engine import PortfolioEngine
from core.risk.risk_engine import RiskEngine
from core.services.runtime.datastore import DataStore
from core.services.runtime.event_codec import (
    build_base_event,
    encode_execution_event,
    encode_order_event,
)
from core.services.trade.exit_service import ExitService
from core.state.state_engine import StateEngine
from core.trigger.trigger_engine import TriggerEngine
from domain.signal import SignalDecision
from strategies.base.simple_strategy import StrategyEngine
from strategies.base.strategy import Strategy


class Runtime:
    def __init__(
        self,
        config: RuntimeConfig | None = None,
        *,
        market_data: MarketDataAdapter,
        broker: BrokerAdapter,
        state: StateEngine | None = None,
        strategy: Strategy | None = None,
        environment: str = "live",
        datastore: DataStore | None = None,
    ) -> None:
        self.config = config or RuntimeConfig()

        self.trigger = TriggerEngine()
        self.portfolio = PortfolioEngine()
        self.risk = RiskEngine()
        self.execution = ExecutionEngine(broker)
        self.state = state or StateEngine(runtime_id=self.config.runtime_id)
        self.exit_service = ExitService()
        self.strategy = strategy or StrategyEngine()
        self.market_data = market_data
        self.environment = environment
        self.datastore = datastore
        self._tick = 0
        self.orders_submitted = 0

    def run_market_once(
        self,
        *,
        stop_loss: float | None = None,
        take_profit: float | None = None,
    ) -> None:
        price = self.market_data.get_last_price(self.config.symbol)
        decision = self.strategy.generate(self.config.symbol, price)
        self.run(decision)

        for position in list(self.state.portfolio.positions.values()):
            exit_order = self.exit_service.create_exit_order(
                position=position,
                current_price=price,
                stop_loss=stop_loss,
                take_profit=take_profit,
            )
            if exit_order is None:
                continue

            exit_result = self.execution.broker.submit_order(exit_order)
            if exit_result.success:
                self.orders_submitted += 1
            self._maybe_append_events(exit_order, exit_result, strategy_name="exit")
            self.state.apply(exit_order, exit_result, strategy_name="exit")
            self._maybe_save_snapshot()

    def run(self, decision: SignalDecision) -> None:
        self._run_decision(decision)

    def _run_decision(self, decision: SignalDecision) -> None:
        trigger_result = self.trigger.process(
            decision,
            runtime_id=self.config.runtime_id,
        )
        allocation = self.portfolio.allocate(
            trigger_result,
            default_quantity=self.config.default_quantity,
        )
        risk_decision = self.risk.evaluate(allocation, portfolio=self.state.portfolio)

        order, exec_result = self.execution.execute(risk_decision)
        if order is not None and exec_result.success:
            self.orders_submitted += 1

        self._maybe_append_events(order, exec_result, strategy_name="main")
        self.state.apply(order, exec_result)
        self._maybe_save_snapshot()

    def _maybe_save_snapshot(self) -> None:
        if self.datastore is None:
            return
        self.datastore.save_portfolio_snapshot(
            ts=self._tick,
            portfolio=self.state.portfolio,
            env=self.environment,
        )
        self._tick += 1

    def _maybe_append_events(
        self,
        order: object | None,
        exec_result: object,
        *,
        strategy_name: str,
    ) -> None:
        if self.datastore is None:
            return

        base = build_base_event(
            ts=self._tick,
            runtime_id=self.config.runtime_id,
            env=self.environment,
            strategy_name=strategy_name,
            symbol=self.config.symbol,
        )

        order_payload = encode_order_event(order)
        if order_payload:
            self.datastore.append_order_event({**base, **order_payload}, env=self.environment)

        exec_payload = encode_execution_event(exec_result)
        # Always append an execution event per tick (stable even when no order).
        self.datastore.append_fill_event({**base, **exec_payload}, env=self.environment)

