from __future__ import annotations

from dataclasses import is_dataclass

from research.run_report import RunReport


def test_run_report_contract() -> None:
    assert is_dataclass(RunReport)

    report = RunReport(
        cycles_run=3,
        orders_submitted=2,
        final_position_qty=1.0,
    )

    assert report.cycles_run == 3
    assert report.orders_submitted == 2
    assert report.final_position_qty == 1.0
