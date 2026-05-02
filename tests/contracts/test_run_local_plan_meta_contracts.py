from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_local import main as run_local_main
from tools.inspect_run import inspect_run


def test_run_local_emits_plan_meta_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    rid = "rt_plan_meta_local"
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
                "--emit-plan-meta",
                "1",
                "--clean",
            ]
        )
        == 0
    )

    report = inspect_run(
        runtime_id=rid,
        store_root=Path("data/store"),
        artifacts_root=Path("data/artifacts"),
        tail=2,
    )
    plan = report.get("plan") if isinstance(report, dict) else None
    assert isinstance(plan, dict)

    # should not be all-null
    assert plan.get("sha256") is not None
    assert isinstance(plan.get("router"), dict)
    assert isinstance(plan.get("universe"), dict)
    assert isinstance(plan.get("strategies"), list)
