from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import (
    ALLOWED_LIFECYCLE_REASONS,
    RISK_MAX_NOTIONAL,
    RISK_MAX_RISK_RATIO,
)
from scripts.run_plan import main as run_plan_main


def _jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        assert isinstance(payload, dict)
        rows.append(payload)
    return rows


def test_risk_reasons_allowlist_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert RISK_MAX_NOTIONAL in ALLOWED_LIFECYCLE_REASONS
    assert RISK_MAX_RISK_RATIO in ALLOWED_LIFECYCLE_REASONS

    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.portfolio_risk_v1.json"
    rid = "rt_risk_reasons_allowlist"
    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    lifecycle = _jsonl(
        tmp_path / "data" / "store" / "live" / rid / "order_lifecycle_events.jsonl"
    )
    reasons = {
        str(event["reason"])
        for event in lifecycle
        if isinstance(event.get("reason"), str)
    }
    assert {RISK_MAX_NOTIONAL, RISK_MAX_RISK_RATIO} <= reasons
    assert reasons <= ALLOWED_LIFECYCLE_REASONS
