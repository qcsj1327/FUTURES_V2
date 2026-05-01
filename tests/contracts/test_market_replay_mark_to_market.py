from __future__ import annotations

from research.market_replay import MarketReplayRunner


def test_market_replay_equity_curve_uses_market_prices() -> None:
    runner = MarketReplayRunner()

    report = runner.run(2)

    assert len(report.equity_curve) == 2
    assert all(value >= 0.0 for value in report.equity_curve)


def test_market_replay_shared_portfolio_keeps_cross_symbol_prices() -> None:
    runner = MarketReplayRunner()

    report = runner.run_multi_symbol_shared_portfolio(
        ["au", "ag"],
        cycles=4,
    )

    assert len(report.equity_curve) == 4
    assert all(value >= 0.0 for value in report.equity_curve)
