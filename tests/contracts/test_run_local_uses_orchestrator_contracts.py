from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_local import main as run_local_main


def test_run_local_all_produces_orchestrated_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    rid = "rt_local_orch"
    assert (
        run_local_main(
            [
                "all",
                "--runtime-id",
                rid,
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
                "--clean",
            ]
        )
        == 0
    )

    assert (tmp_path / "data" / "store" / "live" / rid).exists()
    assert (tmp_path / "data" / "store" / "sandbox" / rid).exists()

    assert (tmp_path / "data" / "artifacts" / "summaries" / f"current_{rid}.json").exists()
    assert (tmp_path / "data" / "artifacts" / "summaries" / f"candidate_{rid}.json").exists()
    approved = list(
        (tmp_path / "data" / "artifacts" / "approved").glob(f"approved_cand_{rid}_*.json")
    )
    assert len(approved) >= 1

    decisions = list((tmp_path / "data" / "artifacts" / "decisions").glob(f"decision_{rid}_*.json"))
    manifests = list((tmp_path / "data" / "artifacts" / "manifests").glob(f"manifest_{rid}_*.json"))
    assert len(decisions) >= 1
    assert len(manifests) >= 1
