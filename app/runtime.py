from __future__ import annotations

from core.execution.execution_engine import ExecutionEngine
from core.risk.risk_engine import RiskEngine
from core.state.state_engine import StateEngine
from core.trigger.trigger_engine import TriggerEngine
from domain.signal import SignalDecision


class Runtime:
    def __init__(self) -> None:
        self.trigger = TriggerEngine()
        self.risk = RiskEngine()
        from adapters.broker.fake_broker import FakeBroker
        self.execution = ExecutionEngine(FakeBroker())
        self.state = StateEngine()

    def run(self, decision: SignalDecision) -> None:
        trigger_result = self.trigger.process(decision, runtime_id="r1")

        risk_decision = self.risk.evaluate(trigger_result)

        order, exec_result = self.execution.execute(risk_decision)

        self.state.apply(order, exec_result)
