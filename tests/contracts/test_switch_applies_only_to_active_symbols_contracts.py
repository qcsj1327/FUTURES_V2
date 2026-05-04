from __future__ import annotations

import json
from datetime import UTC, datetime
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


def test_topn_switch_calendar_switch_applies_only_to_active_symbols_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.topn_switch_calendar.json"
    rid = "rt_switch_active_only"
    approved_dir = tmp_path / "data" / "artifacts" / "strategy_switch"
    approved_dir.mkdir(parents=True, exist_ok=True)
    (approved_dir / f"strategy_switch_approved_{rid}.json").write_text(
        json.dumps(
            {
                "kind": "strategy_switch_approved",
                "runtime_id": rid,
                "approved_at": datetime.now(UTC).isoformat(),
                "active_top_n_symbols": ["au", "ag", "cu"],
                "enabled_strategies_by_symbol": {
                    "au": ["volume_observer_guard"],
                    "ag": ["volume_observer_guard"],
                    "cu": ["volume_observer_guard"],
                    "rb": ["simple_strategy"],
                    "zn": ["simple_strategy"],
                },
            }
        ),
        encoding="utf-8",
    )

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid]) == 0

    base = tmp_path / "data" / "store" / "live" / rid
    order_events = _jsonl(base / "order_events.jsonl")
    score_events = _jsonl(base / "strategy_score_events.jsonl")
    rank_events = _jsonl(base / "rank_events.jsonl")

    assert not order_events
    active_raw = rank_events[-1]["active_symbols"]
    assert isinstance(active_raw, list)
    assert {str(item) for item in active_raw} == {"au", "ag", "cu"}
    assert {
        str(row["symbol"])
        for row in score_events
        if row.get("strategy_name") == "simple_strategy"
    } >= {"rb", "zn"}
