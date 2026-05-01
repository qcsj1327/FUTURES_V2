from __future__ import annotations

from pathlib import Path

import pytest

from research.replay_manifest import main as replay_main
from scripts.run_local import main as run_local_main


def test_replay_manifest_cli_writes_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    rc = run_local_main(
        [
            "all",
            "--clean",
            "--runtime-id",
            "rt_cli",
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

    out_md = tmp_path / "report.md"
    rc2 = replay_main(
        [
            str(manifests[0]),
            "--format",
            "md",
            "--output",
            str(out_md),
        ]
    )
    assert rc2 == 0
    assert out_md.exists()

    text = out_md.read_text(encoding="utf-8")
    assert "# Promotion Replay" in text
    assert "rt_cli" in text
