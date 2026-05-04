from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main


def _jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        assert isinstance(payload, dict)
        rows.append(payload)
    return rows


def test_topn_respects_trading_calendar_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.topn_switch_calendar.json"
    rid = "rt_topn_calendar_contract"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    base = tmp_path / "data" / "store" / "live" / rid
    rank_events = _jsonl(base / "rank_events.jsonl")
    order_events = _jsonl(base / "order_events.jsonl")
    fill_events = _jsonl(base / "fill_events.jsonl")
    lifecycle_events = _jsonl(base / "order_lifecycle_events.jsonl")

    assert rank_events
    active_raw = rank_events[-1]["active_symbols"]
    assert isinstance(active_raw, list)
    active = {str(item) for item in active_raw}
    assert active == {"au", "ag", "cu"}
    excluded_raw = rank_events[-1]["excluded_symbols"]
    assert isinstance(excluded_raw, list)
    excluded = {
        str(item["symbol"]): str(item["reason"])
        for item in excluded_raw
        if isinstance(item, dict)
    }
    assert excluded["rb"] == "non_trading_time"
    assert excluded["zn"] == "non_trading_time"

    for rows in (order_events, fill_events, lifecycle_events):
        assert {str(row["symbol"]) for row in rows} <= active
