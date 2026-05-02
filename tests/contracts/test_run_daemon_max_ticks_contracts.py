from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from app.orchestration.daemon_runner import run_loop
from app.orchestration.session_builder import build_universe_session
from config.defaults import default_plan


def _count_lines(p: Path) -> int:
    if not p.exists():
        return 0
    return sum(1 for _ in p.open("r", encoding="utf-8"))


def test_daemon_respects_max_ticks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rid = "rt_max"
    plan = default_plan(runtime_id=rid)

    ds = plan.datastore
    ds = replace(ds, store_root=tmp_path / "data" / "store")
    plan = replace(plan, datastore=ds)

    session = build_universe_session(plan=plan, env="live", runtime_id=rid)

    monkeypatch.setattr("time.sleep", lambda *_args, **_kwargs: None)

    _ = run_loop(session=session, max_ticks=3, interval_s=1.0, stop_on_exception=True)

    live_snap = tmp_path / "data" / "store" / "live" / rid / "portfolio_snapshots.jsonl"
    assert _count_lines(live_snap) == 3
