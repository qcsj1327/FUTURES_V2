from __future__ import annotations

from research.report_analyzer import ReportAnalyzer
from research.run_report import RunReport


def test_report_analyzer_ranking() -> None:
    analyzer = ReportAnalyzer()

    reports = {
        "a": RunReport(cycles_run=2, orders_submitted=1, final_position_qty=1.0),
        "b": RunReport(cycles_run=2, orders_submitted=3, final_position_qty=3.0),
        "c": RunReport(cycles_run=2, orders_submitted=2, final_position_qty=2.0),
    }

    ranked = analyzer.rank_by_orders(reports)

    assert ranked[0][0] == "b"
    assert ranked[1][0] == "c"
    assert ranked[2][0] == "a"


def test_report_analyzer_position_ranking() -> None:
    analyzer = ReportAnalyzer()

    reports = {
        "a": RunReport(cycles_run=2, orders_submitted=1, final_position_qty=1.0),
        "b": RunReport(cycles_run=2, orders_submitted=3, final_position_qty=3.0),
    }

    ranked = analyzer.rank_by_position(reports)

    assert ranked[0][0] == "b"
