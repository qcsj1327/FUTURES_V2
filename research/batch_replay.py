from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from core.services.reporting import RunReport
from research.replay import ReplayRunner


class BatchReplayRunner:
    def run(
        self,
        jobs: Mapping[str, str | Path],
        output_dir: str | Path | None = None,
    ) -> dict[str, RunReport]:
        results: dict[str, RunReport] = {}

        for name, path in jobs.items():
            output_path = None

            if output_dir is not None:
                output_path = Path(output_dir) / f"{name}_report.csv"

            runner = ReplayRunner()
            report = runner.run_csv(path, output_path)

            results[name] = report

        return results
