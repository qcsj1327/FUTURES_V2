from __future__ import annotations

import json
from pathlib import Path

import pytest

from optimize.promoter.approved_config import write_approved_config


def test_rejected_does_not_write_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    out = write_approved_config(
        approved=False,
        candidate_id="c1",
        candidate_config={"strategy_name": "s", "params": {}},
        decision_deltas={"success_rate_delta": 0.0},
        thresholds={"min_events": 10},
        filename="approved_c1.json",
    )
    assert out is None
    assert not (tmp_path / "data" / "artifacts" / "approved" / "approved_c1.json").exists()


def test_approved_writes_artifact_with_required_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)

    out = write_approved_config(
        approved=True,
        candidate_id="c2",
        candidate_config={"strategy_name": "s", "params": {"x": 1}},
        decision_deltas={"success_rate_delta": 0.12},
        thresholds={"min_events": 2, "max_consecutive_failures": 3},
        current_metrics={"total_events": 2, "success_rate": 0.5},
        candidate_metrics={"total_events": 2, "success_rate": 0.62},
        filename="approved_c2.json",
    )
    assert out is not None
    assert out.exists()

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["kind"] == "approved_config"
    assert payload["schema_version"] == 1
    assert payload["candidate_id"] == "c2"
    assert "created_at" in payload

    assert payload["candidate_config"]["strategy_name"] == "s"
    assert payload["candidate_config"]["params"]["x"] == 1
    assert payload["decision_deltas"]["success_rate_delta"] == pytest.approx(0.12)
    assert payload["thresholds"]["min_events"] == 2

    assert payload["current_metrics"]["success_rate"] == pytest.approx(0.5)
    assert payload["candidate_metrics"]["success_rate"] == pytest.approx(0.62)
