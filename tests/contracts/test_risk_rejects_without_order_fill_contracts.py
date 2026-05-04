from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.execution.lifecycle_reasons import RISK_MAX_NOTIONAL, RISK_MAX_RISK_RATIO
from scripts.run_plan import main as run_plan_main
from tools.inspect_run import inspect_run


def _jsonl(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        assert isinstance(payload, dict)
        rows.append(payload)
    return rows


def test_risk_rejects_without_order_fill_growth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.portfolio_risk_v1.json"
    rid = "rt_risk_rejects_without_order_fill"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0
    base = tmp_path / "data" / "store" / "live" / rid
    order_events = _jsonl(base / "order_events.jsonl")
    fill_events = _jsonl(base / "fill_events.jsonl")
    lifecycle = _jsonl(base / "order_lifecycle_events.jsonl")
    risk_rejects = [
        event
        for event in lifecycle
        if event.get("reason") in {RISK_MAX_NOTIONAL, RISK_MAX_RISK_RATIO}
    ]

    assert len(order_events) == 1
    assert len(fill_events) == 1
    assert risk_rejects
    assert all(event["status"] == "REJECTED" for event in risk_rejects)

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "data" / "store",
        artifacts_root=tmp_path / "data" / "artifacts",
        tail=40,
    )
    assert report["risk_stats"]["live"]["reject_count"] == len(risk_rejects)
