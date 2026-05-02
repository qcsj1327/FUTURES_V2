from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_local import main as run_local_main
from tools.inspect_run import inspect_run


def test_run_local_emits_plan_meta_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    rid = "rt_meta"
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
                "--emit-plan-meta",
                "1",
                "--clean",
            ]
        )
        == 0
    )

    # inspect_run should include plan.router/universe/strategies (not all null)
    report = inspect_run(
        runtime_id=rid,
        store_root=Path("data/store"),
        artifacts_root=Path("data/artifacts"),
        tail=2,
    )
    plan = report.get("plan") if isinstance(report, dict) else None
    assert isinstance(plan, dict)

    assert isinstance(plan.get("router"), dict)
    assert isinstance(plan.get("universe"), dict)
    assert isinstance(plan.get("strategies"), list)

    # also verify manifest has plan field
    mdir = tmp_path / "data" / "artifacts" / "manifests"
    mfiles = sorted(mdir.glob(f"manifest_{rid}_*.json"))
    assert mfiles
    m = json.loads(mfiles[-1].read_text(encoding="utf-8"))
    assert "plan" in m
