from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping

from app.replay import ReplayRunner
from app.run_report import RunReport


class BatchReplayRunner:
    def __init__(self) -> None:
        self.runner = ReplayRunner()

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

            report = self.runner.run_csv(path, output_path)

            results[name] = report

        return results
