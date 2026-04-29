from __future__ import annotations

from research.replay import ReplayRunner


def test_replay_csv() -> None:
    runner = ReplayRunner()

    report = runner.run_csv("data/replay/test_signals.csv")

    assert report.cycles_run == 2
    assert report.orders_submitted == 2
    assert report.final_position_qty > 0
