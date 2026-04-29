from __future__ import annotations

from pathlib import Path

from research.batch_replay import BatchReplayRunner


def test_batch_replay(tmp_path: Path) -> None:
    runner = BatchReplayRunner()

    jobs = {
        "job1": "data/replay/test_signals.csv",
        "job2": "data/replay/test_signals.csv",
    }

    results = runner.run(jobs, output_dir=tmp_path)

    assert "job1" in results
    assert "job2" in results

    assert results["job1"].cycles_run == 2
    assert results["job2"].orders_submitted == 2

    assert (tmp_path / "job1_report.csv").exists()
    assert (tmp_path / "job2_report.csv").exists()
