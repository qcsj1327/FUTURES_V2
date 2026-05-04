from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import RISK_MAX_MARGIN_USED, RISK_MAX_NOTIONAL
from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_risk_promotion_v2_limits_reject_lifecycle_only_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.portfolio_risk_v2.json"
    rid = "rt_risk_lifecycle_only_v2"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    base = tmp_path / "data" / "store" / "live" / rid
    lifecycle = _events(base / "order_lifecycle_events.jsonl")
    orders = _events(base / "order_events.jsonl")
    fills = _events(base / "fill_events.jsonl")
    rejected = [event for event in lifecycle if event.get("status") == "REJECTED"]
    reasons = {str(event.get("reason")) for event in rejected}

    assert RISK_MAX_NOTIONAL in reasons
    assert RISK_MAX_MARGIN_USED in reasons
    assert fills
    assert all(str(event.get("symbol")) != "ag" for event in orders)
    assert all(str(event.get("symbol")) != "ag" for event in fills)
