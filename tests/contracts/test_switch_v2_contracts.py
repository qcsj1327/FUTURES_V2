from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.run_plan import main as run_plan_main
from tools.approve_switch import main as approve_switch_main


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _events(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_switch_v2_requires_approval_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.strategy_switch_v2.json"
    rid = "rt_switch_v2_requires_approval"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    order_path = tmp_path / "data" / "store" / "live" / rid / "order_events.jsonl"
    proposal_path = (
        tmp_path
        / "data"
        / "artifacts"
        / "strategy_switch"
        / f"strategy_switch_proposal_{rid}.json"
    )
    proposal = _read_json(proposal_path)

    assert not _events(order_path)
    assert proposal["kind"] == "strategy_switch_proposal"
    assert proposal["thresholds"] == {
        "min_score": 1.0,
        "max_enabled_strategies_per_symbol": 1,
        "scoring_model": "cost_risk_v2",
        "approval_required": True,
    }
    assert proposal["enabled_strategies_by_symbol"] == {"au": ["simple_strategy"]}


def test_switch_v2_approved_changes_enabled_strategies_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.strategy_switch_v2.json"
    rid = "rt_switch_v2_approved_effect"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0
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

    order_path = tmp_path / "data" / "store" / "live" / rid / "order_events.jsonl"
    orders = _events(order_path)
    assert orders
    assert {str(order.get("strategy_name")) for order in orders} == {"simple_strategy"}
