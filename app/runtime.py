from __future__ import annotations

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from core.execution.execution_engine import ExecutionEngine
from core.risk.risk_engine import RiskEngine
from core.state.state_engine import StateEngine
from core.trigger.trigger_engine import TriggerEngine
from domain.signal import SignalDecision


class Runtime:
    def __init__(self) -> None:
        market_data = SimulatedMarketData()

        self.trigger = TriggerEngine()
        self.risk = RiskEngine()
        self.execution = ExecutionEngine(SimulatedBroker(market_data))
        self.state = StateEngine()
        self.orders_submitted = 0

    def run(self, decision: SignalDecision) -> None:
        trigger_result = self.trigger.process(decision, runtime_id="r1")
        risk_decision = self.risk.evaluate(trigger_result)
        order, exec_result = self.execution.execute(risk_decision)
        if order is not None and exec_result.success:
            self.orders_submitted += 1
        self.state.apply(order, exec_result)
