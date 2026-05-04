from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_topn_calendar_gate_no_execution_for_inactive_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.topn_switch_calendar_v2.json"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_pr31_gate", "--clean"]) == 0

    base = tmp_path / "data" / "store" / "live" / "rt_pr31_gate"
    rank_events = _events(base / "rank_events.jsonl")
    lifecycle_events = _events(base / "order_lifecycle_events.jsonl")
    order_events = _events(base / "order_events.jsonl")
    fill_events = _events(base / "fill_events.jsonl")
    active_symbols = set(cast(list[str], rank_events[-1]["active_symbols"]))

    assert active_symbols == {"ag", "au", "cu"}
    assert all(str(event["symbol"]) in active_symbols for event in order_events)
    assert all(str(event["symbol"]) in active_symbols for event in fill_events)
    assert all(str(event["symbol"]) in active_symbols for event in lifecycle_events)
    excluded_items = cast(list[dict[str, Any]], rank_events[-1]["excluded_symbols"])
    excluded = {
        str(item["symbol"]): str(item["reason"])
        for item in excluded_items
    }
    assert excluded["rb"] == "non_trading_time"
    assert excluded["zn"] == "non_trading_time"
