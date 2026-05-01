from __future__ import annotations

from research.market_replay import MarketReplayRunner
from research.run_report import RunReport


def test_run_report_exposes_equity_metrics() -> None:
    report = RunReport(
        cycles_run=0,
        orders_submitted=0,
        final_position_qty=0.0,
    )

    assert report.equity_curve == []
    assert report.cash_curve == []
    assert report.position_qty_curve == []
    assert report.max_drawdown == 0.0


def test_market_replay_records_curve_per_cycle() -> None:
    runner = MarketReplayRunner()

    report = runner.run(3)

    assert len(report.equity_curve) == 3
    assert len(report.cash_curve) == 3
    assert len(report.position_qty_curve) == 3


def test_market_replay_records_final_position_qty_from_curve() -> None:
    runner = MarketReplayRunner()

    report = runner.run(3)

    assert report.position_qty_curve
    assert report.final_position_qty == report.position_qty_curve[-1]


def test_market_replay_max_drawdown_is_non_negative() -> None:
    runner = MarketReplayRunner()

    report = runner.run(3)

    assert report.max_drawdown >= 0.0
