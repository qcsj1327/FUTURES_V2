from __future__ import annotations

from collections.abc import Iterable

from app.runtime import Runtime
from domain.signal import SignalDecision


class Scheduler:
    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.cycles_run = 0

    def run_once(self, decision: SignalDecision) -> None:
        self.runtime.run(decision)
        self.cycles_run += 1

    def run_many(self, decisions: Iterable[SignalDecision]) -> None:
        for decision in decisions:
            self.run_once(decision)
