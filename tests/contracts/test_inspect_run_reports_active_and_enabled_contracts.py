from __future__ import annotations

from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main
from tools.inspect_run import inspect_run


def test_inspect_run_reports_active_and_enabled_strategies_by_symbol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.topn_switch_calendar.json"
    rid = "rt_inspect_active_enabled"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "data" / "store",
        artifacts_root=tmp_path / "data" / "artifacts",
        tail=30,
    )

    assert report["active_symbols"]["live"] == ["ag", "au", "cu"]
    enabled = report["enabled_strategies_by_symbol"]["live"]
    assert enabled["au"] == ["simple_strategy", "volume_observer_guard"]
    assert enabled["rb"] == ["simple_strategy", "volume_observer_guard"]
    projection_active = report["dashboard_projection"]["active_symbols"]["live"]
    assert projection_active["symbols"] == ["ag", "au", "cu"]
    assert projection_active["source"] in {"rank_events", "strategy_switch_proposal"}
    projection_enabled = report["dashboard_projection"]["strategy_switch"][
        "enabled_strategies_by_symbol"
    ]
    assert projection_enabled["au"] == [
        "simple_strategy",
        "volume_observer_guard",
    ]
