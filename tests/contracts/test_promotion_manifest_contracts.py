from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_local import main


def test_run_local_writes_manifest_and_references_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    rc = main(
        [
            "all",
            "--clean",
            "--runtime-id",
            "rt_manifest",
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
    files = list(mdir.glob("manifest_*.json"))
    assert len(files) >= 1

    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["kind"] == "promotion_manifest"
    assert payload["schema_version"] == 1
    assert payload["runtime_id"] == "rt_manifest"
    assert "candidate_id" in payload
    assert "candidate_config" in payload
    assert "thresholds" in payload

    artifacts = payload["artifacts"]
    for key in ("current_summary", "candidate_summary", "decision", "approved"):
        assert artifacts[key] is not None
        assert (tmp_path / artifacts[key]).exists()
