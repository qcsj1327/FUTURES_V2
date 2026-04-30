from __future__ import annotations

import pytest

from research.market_replay import MarketReplayRunner


def test_market_replay_runs_requested_cycles() -> None:
    runner = MarketReplayRunner()

    report = runner.run(3)

    assert report.cycles_run == 3
    assert report.orders_submitted >= 0
    assert report.final_position_qty >= 0


def test_market_replay_zero_cycles_does_nothing() -> None:
    runner = MarketReplayRunner()

    report = runner.run(0)

    assert report.cycles_run == 0
    assert report.orders_submitted == 0
    assert report.final_position_qty == 0.0


def test_market_replay_rejects_negative_cycles() -> None:
    runner = MarketReplayRunner()

    with pytest.raises(ValueError, match="cycles_must_be_non_negative"):
        runner.run(-1)


def test_market_replay_can_trigger_exit_rules() -> None:
    runner = MarketReplayRunner()

    report = runner.run(
        1,
        stop_loss=10_000.0,
    )

    assert report.cycles_run == 1
    assert report.orders_submitted >= 1
    assert report.final_position_qty == 0.0
