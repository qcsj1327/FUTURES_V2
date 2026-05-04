from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import RISK_MAX_MARGIN_USED
from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_max_margin_used_rejects_lifecycle_only_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.portfolio_risk_v2.json"
    rid = "rt_max_margin_used_contract"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    base = tmp_path / "data" / "store" / "live" / rid
    lifecycle = _events(base / "order_lifecycle_events.jsonl")
    orders = _events(base / "order_events.jsonl")
    fills = _events(base / "fill_events.jsonl")
    margin_rejects = [
        event for event in lifecycle if event.get("reason") == RISK_MAX_MARGIN_USED
    ]

    assert margin_rejects
    assert {event.get("status") for event in margin_rejects} == {"REJECTED"}
    rejected_ids = {event["order_id"] for event in margin_rejects}
    assert rejected_ids.isdisjoint({event.get("order_id") for event in orders})
    assert rejected_ids.isdisjoint({event.get("order_id") for event in fills})
