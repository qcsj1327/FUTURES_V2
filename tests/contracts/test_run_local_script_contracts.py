from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_local import main


def test_run_local_all_writes_artifact_when_forced_thresholds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    # Force approval regardless of SR delta by using a negative improvement threshold.
    # Keep min_events small so we don't need many ticks.
    rc = main(
        [
            "all",
            "--clean",
            "--ticks-live",
            "2",
            "--ticks-sandbox",
            "2",
            "--min-events",
            "1",
            "--min-success-rate-improvement",
            "-1.0",
            "--max-consecutive-failures",
            "99",
            "--write-artifact",
            "1",
            "--candidate-strategy-name",
            "simple_strategy",
            "--candidate-params-json",
            "{}",
        ]
    )
    assert rc == 0

    out_dir = tmp_path / "data" / "artifacts" / "approved"
    assert out_dir.exists()
    files = list(out_dir.glob("approved_*.json"))
    assert len(files) >= 1
