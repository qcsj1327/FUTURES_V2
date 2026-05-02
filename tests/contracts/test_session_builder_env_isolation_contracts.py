from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.orchestration.session_builder import build_universe_session
from config.defaults import default_plan


def _count_lines(p: Path) -> int:
    if not p.exists():
        return 0
    return sum(1 for _ in p.open("r", encoding="utf-8"))


def test_session_builder_env_isolation(tmp_path: Path) -> None:
    rid = "rt_iso"
    plan = default_plan(runtime_id=rid)

    ds = plan.datastore
    ds = replace(
        ds,
        store_root=tmp_path / "data" / "store",
        artifacts_root=tmp_path / "data" / "artifacts",
        approved_dir=tmp_path / "data" / "artifacts" / "approved",
        decisions_dir=tmp_path / "data" / "artifacts" / "decisions",
        summaries_dir=tmp_path / "data" / "artifacts" / "summaries",
        manifests_dir=tmp_path / "data" / "artifacts" / "manifests",
    )
    plan = replace(plan, datastore=ds)

    live = build_universe_session(plan=plan, env="live", runtime_id=rid)
    sandbox = build_universe_session(plan=plan, env="sandbox", runtime_id=rid)

    live.run_tick()
    sandbox.run_tick()

    live_fill = tmp_path / "data" / "store" / "live" / rid / "fill_events.jsonl"
    sandbox_fill = tmp_path / "data" / "store" / "sandbox" / rid / "fill_events.jsonl"

    assert _count_lines(live_fill) == 1
    assert _count_lines(sandbox_fill) == 1
