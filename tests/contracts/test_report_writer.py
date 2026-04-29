from __future__ import annotations

from pathlib import Path

from app.replay import ReplayRunner


def test_replay_writes_csv(tmp_path: Path) -> None:
    runner = ReplayRunner()

    input_csv = "data/replay/test_signals.csv"
    output_csv = tmp_path / "report.csv"

    report = runner.run_csv(input_csv, output_csv)

    assert report.cycles_run == 2
    assert output_csv.exists()

    content = output_csv.read_text()
    assert "cycles_run" in content
    assert "orders_submitted" in content
