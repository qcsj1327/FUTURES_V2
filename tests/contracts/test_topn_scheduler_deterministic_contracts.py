from __future__ import annotations

from pathlib import Path

from scripts.run_plan import main as run_plan_main
from tests.contracts.test_topn_scheduler_no_orders_for_inactive_symbols_contracts import (
    _read_jsonl,
    _write_topn_plan,
)


def test_topn_scheduler_deterministic_contracts(tmp_path: Path) -> None:
    rid = "rt_topn_deterministic"
    plan_path = _write_topn_plan(tmp_path, runtime_id=rid, ticks=12)
    rank_path = tmp_path / "data" / "store" / "live" / rid / "rank_events.jsonl"

    assert run_plan_main(["--config", str(plan_path), "--runtime-id", rid, "--clean"]) == 0
    first = _read_jsonl(rank_path)[:10]

    assert run_plan_main(["--config", str(plan_path), "--runtime-id", rid, "--clean"]) == 0
    second = _read_jsonl(rank_path)[:10]

    assert first == second
