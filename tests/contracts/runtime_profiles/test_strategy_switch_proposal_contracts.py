from __future__ import annotations

import json
from pathlib import Path

from adapters.storage.datastore_fs import JSONLFileDataStore
from app.orchestration.strategy_switch import (
    write_strategy_switch_auto_approved,
    write_strategy_switch_proposal,
)
from core.services.runtime.event_codec import encode_datastore_event


def _score_event(payload: dict[str, object]) -> dict[str, object]:
    return encode_datastore_event(
        base={
            "ts": payload.get("ts", 1),
            "runtime_id": "rt_local",
            "scope": "local",
            "symbol": payload.get("symbol", "au"),
            "strategy_name": payload.get("strategy_name", "strategy"),
            "strategy_id": payload.get("strategy_name", "strategy"),
            "strategy_impl": "test",
        },
        event_type="strategy_score",
        payload_type="strategy_score",
        source="test",
        payload=payload,
    )


def test_strategy_switch_proposal_keeps_current_and_recommended_separate(tmp_path: Path) -> None:
    store = JSONLFileDataStore(root_dir=tmp_path / "store", scope="local", runtime_id="rt_local")
    store.append_strategy_score_event(
        _score_event({
            "ts": 1,
            "symbol": "au",
            "strategy_name": "volume_trend_filter",
            "final_score": 1.2,
            "raw_score": 1.5,
            "cost_penalty": 0.2,
            "risk_penalty": 0.1,
        }),
        scope="local",
    )
    store.append_strategy_score_event(
        _score_event({
            "ts": 1,
            "symbol": "au",
            "strategy_name": "volume_spike_breakout",
            "final_score": 3.0,
            "raw_score": 3.2,
            "cost_penalty": 0.1,
            "risk_penalty": 0.1,
        }),
        scope="local",
    )

    path = write_strategy_switch_proposal(
        runtime_id="rt_local",
        scope="local",
        store=store,
        artifacts_root=tmp_path / "artifacts",
        universe_symbols=["au"],
        active_top_n=0,
        current_enabled_by_symbol={"au": ["volume_trend_filter"]},
        approval_required=True,
        min_score=1.0,
        max_enabled_strategies_per_symbol=1,
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    symbol = payload["symbols"]["au"]
    assert payload["current_enabled_by_symbol"] == {"au": ["volume_trend_filter"]}
    assert payload["enabled_strategies_by_symbol"] == {"au": ["volume_spike_breakout"]}
    assert symbol["current_enabled_strategies"] == ["volume_trend_filter"]
    assert symbol["recommended_enabled_strategies"] == ["volume_spike_breakout"]
    assert symbol["switch_required"] is True


def test_strategy_switch_auto_promotion_writes_approved_artifact(tmp_path: Path) -> None:
    store = JSONLFileDataStore(root_dir=tmp_path / "store", scope="local", runtime_id="rt_local")
    store.append_strategy_score_event(
        _score_event({
            "ts": 1,
            "symbol": "au",
            "strategy_name": "volume_spike_breakout",
            "final_score": 3.0,
        }),
        scope="local",
    )
    proposal = write_strategy_switch_proposal(
        runtime_id="rt_local",
        scope="local",
        store=store,
        artifacts_root=tmp_path / "artifacts",
        universe_symbols=["au"],
        active_top_n=0,
        current_enabled_by_symbol={"au": ["volume_trend_filter"]},
        approval_required=False,
    )

    approved = write_strategy_switch_auto_approved(proposal_path=proposal)
    result = json.loads(approved.read_text(encoding="utf-8"))

    assert result["enabled_strategies_by_symbol"] == {"au": ["volume_spike_breakout"]}
    assert result["promotion_mode"] == "automatic"
    assert approved.exists()
