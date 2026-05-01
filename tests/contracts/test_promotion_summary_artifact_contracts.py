from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_local import main


def test_run_local_writes_summary_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "all",
            "--clean",
            "--runtime-id",
            "rt_summary",
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
            "--write-artifact",
            "1",
        ]
    )
    assert rc == 0

    sdir = tmp_path / "data" / "artifacts" / "summaries"
    assert sdir.exists()

    cur = sdir / "current_rt_summary.json"
    cand = sdir / "candidate_rt_summary.json"
    assert cur.exists()
    assert cand.exists()

    payload = json.loads(cur.read_text(encoding="utf-8"))
    assert payload["kind"] == "promotion_summary"
    assert payload["schema_version"] == 1
    assert payload["runtime_id"] == "rt_summary"
    assert payload["role"] == "current"

    summary = payload["summary"]
    for k in ("total_events", "success_rate", "max_consecutive_failures"):
        assert k in summary
