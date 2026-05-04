from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from scripts.run_plan import main as run_plan_main


def _events(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_score_cost_risk_fields_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    cfg = Path(__file__).resolve().parents[2] / "plans" / "dev.strategy_switch_v2.json"
    rid = "rt_score_cost_risk_v2"

    assert run_plan_main(["--config", str(cfg), "--runtime-id", rid, "--clean"]) == 0

    rows = _events(tmp_path / "data" / "store" / "live" / rid / "strategy_score_events.jsonl")
    assert rows
    sample = rows[-1]
    for key in ("raw_score", "cost_penalty", "risk_penalty", "final_score", "score"):
        assert key in sample
        assert isinstance(sample[key], (int, float))
    raw_score = cast(float, sample["raw_score"])
    cost_penalty = cast(float, sample["cost_penalty"])
    risk_penalty = cast(float, sample["risk_penalty"])
    final_score = cast(float, sample["final_score"])
    assert sample["score"] == sample["final_score"]
    assert final_score == pytest.approx(raw_score - cost_penalty - risk_penalty)
