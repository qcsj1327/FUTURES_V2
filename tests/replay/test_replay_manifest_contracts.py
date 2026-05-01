from __future__ import annotations

from pathlib import Path

import pytest

from research.replay_manifest import replay_manifest
from scripts.run_local import main


def test_replay_manifest_reads_artifacts_and_returns_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "all",
            "--clean",
            "--runtime-id",
            "rt_replay",
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
            "--write-summary",
            "1",
            "--write-decision",
            "1",
            "--write-manifest",
            "1",
            "--write-artifact",
            "1",
        ]
    )
    assert rc == 0

    mdir = tmp_path / "data" / "artifacts" / "manifests"
    manifests = list(mdir.glob("manifest_*.json"))
    assert len(manifests) >= 1

    report = replay_manifest(manifests[0])

    assert report.runtime_id == "rt_replay"
    assert report.candidate_id.startswith("cand_rt_replay_")
    assert isinstance(report.approved, bool)
    assert isinstance(report.reasons, list)
    assert isinstance(report.current_summary, dict)
    assert isinstance(report.candidate_summary, dict)

    # minimal fields used by gate
    assert "total_events" in report.current_summary
    assert "success_rate" in report.current_summary
    assert "max_consecutive_failures" in report.current_summary
