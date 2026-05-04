from __future__ import annotations

from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import BLOCKED_BY_PENDING_ORDER, RISK_POSITION_LIMIT
from scripts.run_plan import main as run_plan_main
from tools.inspect_run import inspect_run


def test_lifecycle_stats_are_reported_by_inspect_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.risk_pending_guard.json"
    assert (
        run_plan_main(["--config", str(cfg), "--runtime-id", "rt_lifecycle_stats", "--clean"])
        == 0
    )

    report = inspect_run(
        runtime_id="rt_lifecycle_stats",
        store_root=tmp_path / "data" / "store",
        artifacts_root=tmp_path / "data" / "artifacts",
        tail=50,
    )

    assert report["live_order_lifecycle_status_counts"]["REJECTED"] >= 1
    assert report["lifecycle_stats"]["live"]["status_counts"]["REJECTED"] >= 1
    reasons = {item["reason"] for item in report["live_top_lifecycle_reasons"]}
    assert BLOCKED_BY_PENDING_ORDER in reasons
    assert RISK_POSITION_LIMIT in reasons
