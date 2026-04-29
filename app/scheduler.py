from __future__ import annotations

from app.runtime import Runtime
from domain.signal import SignalDecision


class Scheduler:
    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime

    def run_once(self, decision: SignalDecision) -> None:
        self.runtime.run(decision)
