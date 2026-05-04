from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from core.execution.lifecycle_reasons import HALTED_BY_GUARD
from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_halted_by_guard_stops_orders_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.halt_guard_demo.json"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_halt_guard", "--clean"]) == 0

    base = tmp_path / "data" / "store" / "live" / "rt_halt_guard"
    lifecycle = _events(base / "order_lifecycle_events.jsonl")
    orders = _events(base / "order_events.jsonl")
    halted = [event for event in lifecycle if event.get("reason") == HALTED_BY_GUARD]

    assert halted
    first_halted_ts = min(int(cast(int | float | str, event["ts"])) for event in halted)
    halted_ticks = {first_halted_ts, first_halted_ts + 1}
    assert all(
        int(cast(int | float | str, order["ts"])) not in halted_ticks
        for order in orders
    )
