from __future__ import annotations

from collections.abc import Iterable

from adapters.storage.csv_signal_loader import CSVSignalLoader
from app.run_report import RunReport
from app.runtime import Runtime
from app.scheduler import Scheduler
from domain.signal import SignalDecision


class ReplayRunner:
    def __init__(self, runtime: Runtime | None = None) -> None:
        self.runtime = runtime or Runtime()
        self.scheduler = Scheduler(self.runtime)

    def run(self, decisions: Iterable[SignalDecision]) -> RunReport:
        return self.scheduler.run_many(decisions)

    def run_csv(self, path: str) -> RunReport:
        loader = CSVSignalLoader()
        decisions = list(loader.load(path))
        return self.scheduler.run_many(decisions)
