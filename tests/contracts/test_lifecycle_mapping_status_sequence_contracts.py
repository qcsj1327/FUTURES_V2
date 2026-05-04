from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_lifecycle_mapping_status_sequence_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.order_lifecycle_v2.json"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_pr31_sequence", "--clean"]) == 0

    path = (
        tmp_path
        / "data"
        / "store"
        / "live"
        / "rt_pr31_sequence"
        / "order_lifecycle_events.jsonl"
    )
    statuses = [str(event["status"]) for event in _events(path)]

    assert statuses[:3] == ["NEW", "SUBMITTED", "PARTIAL"]
    assert "EXPIRED" in statuses or "FILLED" in statuses
