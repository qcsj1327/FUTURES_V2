from __future__ import annotations

from research.market_replay import MarketReplayRunner
from research.run_report import RunReport


def test_market_replay_runs_many_symbols() -> None:
    reports = MarketReplayRunner().run_many_symbols(
        ["au", "ag"],
        cycles=2,
    )

    assert set(reports) == {"au", "ag"}
    assert all(isinstance(report, RunReport) for report in reports.values())
    assert all(report.cycles_run == 2 for report in reports.values())


def test_market_replay_many_symbols_are_independent() -> None:
    reports = MarketReplayRunner().run_many_symbols(
        ["au", "ag"],
        cycles=3,
    )

    assert reports["au"] is not reports["ag"]
    assert len(reports["au"].equity_curve) == 3
    assert len(reports["ag"].equity_curve) == 3


def test_market_replay_many_symbols_rejects_negative_cycles() -> None:
    try:
        MarketReplayRunner().run_many_symbols(["au"], cycles=-1)
    except ValueError as exc:
        assert str(exc) == "cycles_must_be_non_negative"
    else:
        raise AssertionError("expected ValueError")


def test_market_replay_many_symbols_allows_empty_symbol_list() -> None:
    reports = MarketReplayRunner().run_many_symbols([], cycles=2)

    assert reports == {}
