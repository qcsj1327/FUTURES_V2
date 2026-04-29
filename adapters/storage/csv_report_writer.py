from __future__ import annotations

import csv
from pathlib import Path

from app.run_report import RunReport


class CSVReportWriter:
    def write(self, report: RunReport, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with path.open("w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["cycles_run", "orders_submitted", "final_position_qty"],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "cycles_run": report.cycles_run,
                    "orders_submitted": report.orders_submitted,
                    "final_position_qty": report.final_position_qty,
                }
            )
