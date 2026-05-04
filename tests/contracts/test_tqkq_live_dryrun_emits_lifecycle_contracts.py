from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_tqkq_live_dryrun_emits_lifecycle_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.tqkq_live_dryrun.json"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_pr31_dryrun", "--clean"]) == 0

    path = (
        tmp_path
        / "data"
        / "store"
        / "live"
        / "rt_pr31_dryrun"
        / "order_lifecycle_events.jsonl"
    )
    events = _events(path)
    statuses = {str(event["status"]) for event in events}
    trade_ids = {str(event["trade_instrument_id"]) for event in events}

    assert "SUBMITTED" in statuses
    assert "EXPIRED" in statuses
    assert trade_ids == {"SHFE.au2406"}
