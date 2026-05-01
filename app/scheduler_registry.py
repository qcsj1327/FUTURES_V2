from __future__ import annotations

from collections.abc import Iterable

from app.runtime_registry import RuntimeRegistry
from domain.signal import SignalDecision
from tools.run_report import RunReport


class RegistryScheduler:
    def __init__(self, registry: RuntimeRegistry) -> None:
        self.registry = registry

    def run(self, decisions_map: dict[str, Iterable[SignalDecision]]) -> dict[str, RunReport]:
        reports: dict[str, RunReport] = {}

        for runtime_id, decisions in decisions_map.items():
            runtime = self.registry.get(runtime_id)

            from app.scheduler import Scheduler

            scheduler = Scheduler(runtime)
            report = scheduler.run_many(decisions)

            reports[runtime_id] = report

        return reports
