from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import (
    ALLOWED_LIFECYCLE_REASONS,
    BLOCKED_BY_PENDING_ORDER,
    DUPLICATE_SAME_TICK,
    EXPIRED,
    NEW,
    ORDER_SUBMITTED,
    RISK_POSITION_LIMIT,
    SIMULATED_FILL,
)
from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_lifecycle_reason_enum_contains_runtime_reasons() -> None:
    expected = {
        NEW,
        ORDER_SUBMITTED,
        SIMULATED_FILL,
        EXPIRED,
        RISK_POSITION_LIMIT,
        BLOCKED_BY_PENDING_ORDER,
        DUPLICATE_SAME_TICK,
    }
    assert expected <= ALLOWED_LIFECYCLE_REASONS


def test_lifecycle_reason_enum_all_written_reasons_are_allowlisted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.risk_pending_guard.json"
    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_reason_enum", "--clean"]) == 0

    path = tmp_path / "data" / "store" / "live" / "rt_reason_enum" / "order_lifecycle_events.jsonl"
    reasons = {
        str(e["reason"])
        for e in _events(path)
        if isinstance(e.get("reason"), str)
    }
    assert reasons
    assert reasons <= ALLOWED_LIFECYCLE_REASONS
