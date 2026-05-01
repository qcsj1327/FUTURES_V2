from __future__ import annotations

from adapters.broker.base import BrokerAdapter
from adapters.marketdata.base import MarketDataAdapter
from app.runtime_config import RuntimeConfig
from core.execution.execution_engine import ExecutionEngine
from core.portfolio.portfolio_engine import PortfolioEngine
from core.risk.risk_engine import RiskEngine
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
            self.state.apply(exit_order, exit_result, strategy_name="exit")

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

        self.state.apply(order, exec_result)
