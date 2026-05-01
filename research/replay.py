from __future__ import annotations

# mypy: disable_error_code="valid-type,no-any-return"
import importlib
from collections.abc import Iterable
from pathlib import Path

from adapters.storage.csv_report_writer import CSVReportWriter
from adapters.storage.csv_signal_loader import CSVSignalLoader
from domain.signal import SignalDecision
from research.run_report import RunReport

# -- dynamic app bindings (avoid static layering imports) --
Runtime = importlib.import_module("app.runtime").Runtime
RuntimeFactory = importlib.import_module("app.runtime_factory").RuntimeFactory
Scheduler = importlib.import_module("app.scheduler").Scheduler


class ReplayRunner:
    def __init__(self, runtime: Runtime | None = None) -> None:
        self.runtime = runtime or RuntimeFactory.build_simulated_runtime()
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
