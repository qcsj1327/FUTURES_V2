from __future__ import annotations

from pathlib import Path

from scripts.run_plan import main as run_plan_main
from tests.contracts.test_topn_scheduler_no_orders_for_inactive_symbols_contracts import (
    _write_topn_plan,
)
from tools.inspect_run import inspect_run
from web.api.events import get_run_events


def test_rank_events_emitted_contracts(tmp_path: Path) -> None:
    rid = "rt_rank_events"
    plan_path = _write_topn_plan(tmp_path, runtime_id=rid, ticks=8)

    assert run_plan_main(["--config", str(plan_path), "--runtime-id", rid, "--clean"]) == 0

    store_root = tmp_path / "data" / "store"
    artifacts_root = tmp_path / "data" / "artifacts"
    report = inspect_run(
        runtime_id=rid,
        store_root=store_root,
        artifacts_root=artifacts_root,
        tail=3,
    )
    live_store = report["stores"]["live"]
    assert live_store["stats"]["rank_events_lines"] == 8
    assert len(live_store["tail"]["rank_events"]) == 3

    events = get_run_events(
        runtime_id=rid,
        env="live",
        store_root=store_root,
        event_type="rank",
        tail=20,
    )
    assert events["rank_events"]
    assert events["timeline_filtered_total"] == 8
    assert all(ev["event_type"] == "rank" for ev in events["timeline"])
