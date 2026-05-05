from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import HALTED_BY_GUARD, RATE_LIMITED
from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_execution_guard_rate_limit_and_halt_lifecycle_only_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = (
        Path(__file__).resolve().parents[2]
        / "plans"
        / "dev.tqkq_live_guard_demo.json"
    )
    rid = "rt_tqkq_live_guard"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    base = tmp_path / "data" / "store" / "live" / rid
    lifecycle = _events(base / "order_lifecycle_events.jsonl")
    orders = _events(base / "order_events.jsonl")
    fills = _events(base / "fill_events.jsonl")
    rate_limited = [event for event in lifecycle if event.get("reason") == RATE_LIMITED]
    halted = [event for event in lifecycle if event.get("reason") == HALTED_BY_GUARD]

    assert rate_limited
    assert halted
    assert {event.get("status") for event in rate_limited + halted} == {"REJECTED"}
    guard_reject_ids = {event["order_id"] for event in rate_limited + halted}
    assert guard_reject_ids.isdisjoint({event.get("order_id") for event in orders})
    assert guard_reject_ids.isdisjoint({event.get("order_id") for event in fills})
