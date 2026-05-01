from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_local import main


def test_run_local_writes_decision_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "all",
            "--clean",
            "--runtime-id",
            "rt_decision",
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
            "--write-decision",
            "1",
            "--write-artifact",
            "1",
        ]
    )
    assert rc == 0

    dec_dir = tmp_path / "data" / "artifacts" / "decisions"
    assert dec_dir.exists()
    files = list(dec_dir.glob("decision_*.json"))
    assert len(files) >= 1
