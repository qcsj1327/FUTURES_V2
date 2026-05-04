from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main
from tools.approve_switch import main as approve_switch_main
from web.api.events import get_run_events


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    out: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        assert isinstance(payload, dict)
        out.append(payload)
    return out


def test_strategy_switch_proposal_and_approved_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.strategy_switch.json"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", "rt_switch_schema", "--clean"]) == 0

    proposal_path = (
        tmp_path
        / "data"
        / "artifacts"
        / "strategy_switch"
        / "strategy_switch_proposal_rt_switch_schema.json"
    )
    proposal = _read_json(proposal_path)
    assert proposal["kind"] == "strategy_switch_proposal"
    assert proposal["runtime_id"] == "rt_switch_schema"
    assert proposal["active_top_n_symbols"] == ["au"]
    enabled = proposal["enabled_strategies_by_symbol"]
    assert isinstance(enabled, dict)
    assert enabled["au"] == ["simple_strategy"]

    approved_path = proposal_path.with_name("strategy_switch_approved_rt_switch_schema.json")
    assert approve_switch_main([str(proposal_path), "--output", str(approved_path)]) == 0
    approved = _read_json(approved_path)
    assert approved["kind"] == "strategy_switch_approved"
    assert approved["runtime_id"] == "rt_switch_schema"
    assert approved["enabled_strategies_by_symbol"] == {"au": ["simple_strategy"]}


def test_strategy_switch_approved_changes_order_strategy_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.strategy_switch.json"
    rid = "rt_switch_effect"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0
    order_path = tmp_path / "data" / "store" / "live" / rid / "order_events.jsonl"
    before = _jsonl(order_path)
    assert not before

    proposal_path = (
        tmp_path
        / "data"
        / "artifacts"
        / "strategy_switch"
        / f"strategy_switch_proposal_{rid}.json"
    )
    approved_path = proposal_path.with_name(f"strategy_switch_approved_{rid}.json")
    assert approve_switch_main([str(proposal_path), "--output", str(approved_path)]) == 0

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid]) == 0
    after = _jsonl(order_path)
    assert after
    assert {str(x.get("strategy_name")) for x in after} == {"simple_strategy"}


def test_strategy_score_events_are_emitted_and_web_filterable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.strategy_switch.json"
    rid = "rt_strategy_score_events"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    score_path = tmp_path / "data" / "store" / "live" / rid / "strategy_score_events.jsonl"
    rows = _jsonl(score_path)
    assert rows
    sample = rows[0]
    for key in (
        "event_type",
        "ts",
        "runtime_id",
        "env",
        "symbol",
        "strategy_name",
        "strategy_id",
        "decision",
        "strength",
        "confidence",
        "score",
    ):
        assert key in sample
    assert sample["event_type"] == "strategy_score"

    events = get_run_events(
        runtime_id=rid,
        env="live",
        store_root=tmp_path / "data" / "store",
        event_type="strategy_score",
    )
    assert events["strategy_score_events"]
    assert events["timeline"]
    assert all(x["event_type"] == "strategy_score" for x in events["timeline"])
