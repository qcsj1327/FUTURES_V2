from __future__ import annotations

from research.market_replay import MarketReplayRunner


def test_multi_symbol_shared_portfolio_runs() -> None:
    report = MarketReplayRunner().run_multi_symbol_shared_portfolio(
        ["au", "ag"],
        cycles=4,
    )

    assert report.cycles_run == 4
    assert report.orders_submitted >= 0
    assert report.final_position_qty >= 0.0


def test_multi_symbol_uses_single_equity_curve() -> None:
    report = MarketReplayRunner().run_multi_symbol_shared_portfolio(
        ["au", "ag"],
        cycles=5,
    )

    assert len(report.equity_curve) == 5
    assert len(report.cash_curve) == 5


def test_multi_symbol_shared_portfolio_accumulates_positions() -> None:
    report = MarketReplayRunner().run_multi_symbol_shared_portfolio(
        ["au", "ag"],
        cycles=5,
    )

    assert report.final_position_qty >= 0.0
    assert len(report.position_qty_curve) == 5
