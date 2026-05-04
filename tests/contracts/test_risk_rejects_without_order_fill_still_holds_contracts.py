from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import RISK_MAX_NOTIONAL
from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_risk_rejects_without_order_fill_still_holds_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.halt_guard_demo.json"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_risk_only", "--clean"]) == 0

    base = tmp_path / "data" / "store" / "live" / "rt_risk_only"
    lifecycle = _events(base / "order_lifecycle_events.jsonl")
    orders = _events(base / "order_events.jsonl")
    fills = _events(base / "fill_events.jsonl")
    risk_rejects = [
        event for event in lifecycle if event.get("reason") == RISK_MAX_NOTIONAL
    ]

    assert risk_rejects
    assert all(str(event.get("symbol")) != "ag" for event in orders)
    assert all(str(event.get("symbol")) != "ag" for event in fills)
