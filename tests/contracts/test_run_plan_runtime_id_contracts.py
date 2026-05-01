from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main


def test_run_plan_runtime_id_is_respected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    rid = "rt_plan_contract"
    rc = run_plan_main(["--runtime-id", rid, "--clean"])
    assert rc == 0

    live_dir = tmp_path / "data" / "store" / "live" / rid
    sandbox_dir = tmp_path / "data" / "store" / "sandbox" / rid
    assert live_dir.exists()
    assert sandbox_dir.exists()

    artifacts = tmp_path / "data" / "artifacts"
    assert (artifacts / "summaries" / f"current_{rid}.json").exists()
    assert (artifacts / "summaries" / f"candidate_{rid}.json").exists()

    assert (artifacts / "approved" / f"approved_cand_{rid}.json").exists()

    assert len(list((artifacts / "decisions").glob(f"decision_{rid}_*.json"))) >= 1
    assert len(list((artifacts / "manifests").glob(f"manifest_{rid}_*.json"))) >= 1
