from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from adapters.storage.csv_report_writer import CSVReportWriter
from adapters.storage.csv_signal_loader import CSVSignalLoader
from app.runtime import Runtime
from app.scheduler import Scheduler
from domain.signal import SignalDecision
from research.run_report import RunReport


class ReplayRunner:
    def __init__(self, runtime: Runtime | None = None) -> None:
        self.runtime = runtime or Runtime()
        self.scheduler = Scheduler(self.runtime)

    def run(self, decisions: Iterable[SignalDecision]) -> RunReport:
        return self.scheduler.run_many(decisions)

    def run_csv(self, path: str | Path, output_path: str | Path | None = None) -> RunReport:
        loader = CSVSignalLoader()
        decisions = list(loader.load(path))
        report = self.scheduler.run_many(decisions)

        if output_path is not None:
            CSVReportWriter().write(report, output_path)

        return report
