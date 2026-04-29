from __future__ import annotations

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from app.runtime_config import RuntimeConfig
from core.execution.execution_engine import ExecutionEngine
from core.risk.risk_engine import RiskEngine
from core.state.state_engine import StateEngine
from core.trigger.trigger_engine import TriggerEngine
from domain.signal import SignalDecision
from strategies.base.simple_strategy import StrategyEngine


class Runtime:
    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig()
        market_data = SimulatedMarketData()

        self.trigger = TriggerEngine()
        self.risk = RiskEngine()
        self.execution = ExecutionEngine(SimulatedBroker(market_data))
        self.state = StateEngine()
        self.strategy = StrategyEngine()
        self.market_data = market_data
        self.orders_submitted = 0

    def run(self, decision: SignalDecision) -> None:
        self._run_decision(decision)

    def _run_decision(self, decision: SignalDecision) -> None:
        trigger_result = self.trigger.process(decision, runtime_id=self.config.runtime_id)
        risk_decision = self.risk.evaluate(
            trigger_result,
            quantity=self.config.default_quantity,
        )
        order, exec_result = self.execution.execute(risk_decision)
        if order is not None and exec_result.success:
            self.orders_submitted += 1
        self.state.apply(order, exec_result)
