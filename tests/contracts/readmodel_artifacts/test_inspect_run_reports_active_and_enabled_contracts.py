from __future__ import annotations

import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from core.services.runtime.event_codec import encode_datastore_event
from domain.enums import PositionSide
from domain.state import PortfolioState, PositionKey, PositionState
from web.api.runs import list_runs
from web.readmodel.dashboard import _execution_observability, inspect_run


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if "envelope" not in payload:
        scope = path.parts[-3]
        runtime_id = path.parts[-2]
        stem = path.name.removesuffix(".jsonl")
        payload_type = {
            "order_events": "order_event",
            "fill_events": "fill_event",
            "order_lifecycle_events": "order_lifecycle",
            "rank_events": "rank",
            "strategy_score_events": "strategy_score",
            "portfolio_snapshots": "snapshot",
            "metrics": "observation",
        }.get(stem, stem.removesuffix("_events"))
        payload = encode_datastore_event(
            base={
                "ts": int(payload.get("ts", 0) or 0),
                "runtime_id": runtime_id,
                "scope": scope,
                "symbol": str(payload.get("symbol") or payload.get("instrument_id") or ""),
                "strategy_name": str(payload.get("strategy_name") or "contract"),
                "strategy_impl": "contract",
            },
            event_type=payload_type,
            payload_type=payload_type,
            source="contract",
            payload=payload,
        )
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _ts(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("Asia/Shanghai")).timestamp())


def _write_manifest(root: Path, runtime_id: str, plan_cfg: dict[str, Any]) -> None:
    artifacts = root / "data" / "artifacts"
    scope = plan_cfg.get("runtime", {}).get("mode", "live")
    approved = artifacts / scope / "strategy_switch" / f"strategy_switch_approved_{runtime_id}.json"
    _write_json(
        approved,
        {
            "kind": "strategy_switch_approved",
            "schema_version": 1,
            "runtime_id": runtime_id,
            "runtime_profile": scope,
            "datastore_scope": scope,
            "is_live": scope == "live",
            "generated_at": "2026-05-08T00:00:00+00:00",
            "enabled_strategies_by_symbol": {
                "au": ["simple_strategy", "volume_observer_guard"],
                "rb": ["simple_strategy", "volume_observer_guard"],
            },
        },
    )
    _write_json(
        artifacts / "manifests" / f"manifest_{runtime_id}_20260508T000000Z.json",
        {
            "kind": "promotion_manifest",
            "runtime_id": runtime_id,
            "runtime_profile": scope,
            "datastore_scope": scope,
            "is_live": scope == "live",
            "created_at": "2026-05-08T00:00:00+00:00",
            "candidate_id": "cand_test",
            "status": "running",
            "plan": {
                "path": "plan.json",
                "sha256": "sha",
                "effective_config_summary": plan_cfg,
                "redaction_status": {"redacted": True},
            },
            "artifacts": {
                "current_summary": None,
                "candidate_summary": None,
                "decision": None,
                "approved": None,
                "strategy_switch_proposal": None,
                "strategy_switch_approved": str(approved),
            },
        },
    )


def test_inspect_run_reports_active_and_enabled_strategies_by_symbol(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    rid = "rt_inspect_active_enabled"
    plan_cfg = {
        "runtime": {"mode": "live", "active_top_n": 3},
        "universe": {"symbols": ["ag", "au", "cu", "rb"]},
        "router": {"mode": "priority"},
        "strategies": [
            {"name": "simple_strategy", "symbols": ["ag", "au", "cu", "rb"]},
            {"name": "volume_observer_guard", "symbols": ["au", "rb"]},
        ],
    }
    _write_manifest(tmp_path, rid, plan_cfg)
    _append_jsonl(
        tmp_path / "data" / "store" / "live" / rid / "rank_events.jsonl",
        {
            "event_type": "rank",
            "ts": 1,
            "runtime_id": rid,
            "runtime_profile": "live",
            "datastore_scope": "live",
            "active_symbols": ["ag", "au", "cu"],
        },
    )

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "data" / "store",
        artifacts_root=tmp_path / "data" / "artifacts",
        tail=30,
    )

    assert report["active_symbols"]["live"] == ["ag", "au", "cu"]
    enabled = report["enabled_strategies_by_symbol"]["live"]
    assert enabled["au"] == ["simple_strategy", "volume_observer_guard"]
    assert enabled["rb"] == ["simple_strategy", "volume_observer_guard"]
    projection_active = report["dashboard_projection"]["active_symbols"]["live"]
    assert projection_active["symbols"] == ["ag", "au", "cu"]
    assert projection_active["source"] == "rank_events"
    projection_enabled = report["dashboard_projection"]["strategy_switch"][
        "enabled_strategies_by_symbol"
    ]
    assert projection_enabled["au"] == [
        "simple_strategy",
        "volume_observer_guard",
    ]


def test_local_profile_reports_simulated_execution_mode() -> None:
    execution = _execution_observability(
        {
            "runtime": {"mode": "local"},
            "adapters": {
                "market_data": {"mode": "local_file"},
                "broker": {"mode": "simulated"},
            },
        }
    )

    assert execution["broker_type"] == "simulated"
    assert execution["execution_mode"] == "simulated"
    assert execution["confirm_live"] is False


def test_inspect_run_uses_redacted_manifest_summary_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    rid = "rt_redacted_dryrun"
    artifacts = tmp_path / "data" / "artifacts"
    _write_json(
        artifacts / "manifests" / f"manifest_{rid}_20260508T000000Z.json",
        {
            "kind": "promotion_manifest",
            "runtime_id": rid,
            "runtime_profile": "dryrun",
            "datastore_scope": "dryrun",
            "created_at": "2026-05-08T00:00:00+00:00",
            "candidate_id": "cand_test",
            "status": "running",
            "plan": {
                "path": "plans/dev.dryrun.json",
                "sha256": "sha",
                "effective_config_summary": {
                    "runtime_profile": "dryrun",
                    "datastore_scope": "dryrun",
                    "runtime": {"mode": "dryrun", "active_top_n": 0},
                    "universe": {"symbols": ["au"]},
                    "adapters": {
                        "broker": {
                            "mode": "tqkq",
                            "submit_mode": "dryrun",
                            "confirm_live_token": {"present": True, "length": 18},
                        }
                    },
                },
                "redaction_status": {"redacted": True},
            },
            "artifacts": {
                "current_summary": None,
                "candidate_summary": None,
                "decision": None,
                "approved": None,
                "strategy_switch_proposal": None,
                "strategy_switch_approved": None,
            },
        },
    )

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "data" / "store",
        artifacts_root=artifacts,
        tail=30,
    )

    execution = report["dashboard_projection"]["execution_state"]
    assert execution["runtime_profile"] == "dryrun"
    assert execution["datastore_scope"] == "dryrun"
    assert execution["execution_mode"] == "dryrun"
    assert execution["broker_type"] == "tqkq"
    assert execution["confirm_live_token_present"] is True


def test_inspect_run_reads_enveloped_snapshot_and_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    rid = "rt_enveloped_readmodel"
    plan_cfg = {
        "runtime": {"mode": "local"},
        "universe": {"symbols": ["au"]},
        "strategies": [{"name": "simple_strategy", "symbols": ["au"]}],
    }
    _write_manifest(tmp_path, rid, plan_cfg)

    store = tmp_path / "data" / "store" / "local" / rid
    snapshot_rel = "snapshots/portfolio_1.pkl"
    snapshot_path = store / snapshot_rel
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    key = PositionKey("au", "SHFE.au2606", PositionSide.LONG)
    portfolio = PortfolioState(
        runtime_id=rid,
        positions={
            key: PositionState(
                instrument_id="au",
                trade_instrument_id="SHFE.au2606",
                position_side=PositionSide.LONG,
                quantity=2.0,
                avg_price=580.0,
                runtime_id=rid,
            )
        },
    )
    snapshot_path.write_bytes(pickle.dumps(portfolio))
    _append_jsonl(
        store / "portfolio_snapshots.jsonl",
        {
            "envelope": {
                "schema_version": "1",
                "event_id": "snap-1",
                "event_type": "snapshot",
                "runtime_id": rid,
                "runtime_profile": "local",
                "datastore_scope": "local",
                "execution_env": "simulated",
                "broker_profile": "simulated",
                "submit_mode": "none",
                "is_live": False,
                "is_simulated_execution": True,
                "generated_at": "2026-05-08T00:00:00+00:00",
                "source": "datastore",
                "payload_type": "snapshot",
            },
            "payload": {
                "ts": 1,
                "runtime_id": rid,
                "portfolio_file": snapshot_rel,
            },
        },
    )
    _append_jsonl(
        store / "order_events.jsonl",
        {
            "envelope": {
                "schema_version": "1",
                "event_id": "order-1",
                "event_type": "order",
                "runtime_id": rid,
                "runtime_profile": "local",
                "datastore_scope": "local",
                "execution_env": "simulated",
                "broker_profile": "simulated",
                "submit_mode": "none",
                "is_live": False,
                "is_simulated_execution": True,
                "generated_at": "2026-05-08T00:00:01+00:00",
                "source": "runtime",
                "payload_type": "order_event",
            },
            "payload": {
                "ts": 2,
                "symbol": "au",
                "instrument_id": "au",
                "trade_instrument_id": "SHFE.au2606",
                "market_price": 581.0,
            },
        },
    )

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "data" / "store",
        artifacts_root=tmp_path / "data" / "artifacts",
        tail=30,
    )

    projection = report["dashboard_projection"]
    positions = projection["positions"]["local"]
    assert positions["empty_reason"] is None
    assert positions["items"][0]["quantity"] == 2.0
    quotes = projection["quotes"]["local"]
    assert quotes["source_scope_unknown"] is False
    assert quotes["source_event_ids"] == ["order-1"]
    assert quotes["payload_types"] == ["order_event"]


def test_run_list_uses_redacted_manifest_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    artifacts = tmp_path / "data" / "artifacts"
    _write_json(
        artifacts / "manifests" / "manifest_rt_local_20260508T000000Z.json",
        {
            "kind": "promotion_manifest",
            "runtime_id": "rt_local",
            "runtime_profile": "local",
            "datastore_scope": "local",
            "created_at": "2026-05-08T00:00:00+00:00",
            "candidate_id": "cand_test",
            "status": "running",
            "plan": {
                "path": "plans/dev.local.json",
                "sha256": "sha",
                "effective_config_summary": {
                    "runtime_profile": "local",
                    "datastore_scope": "local",
                    "runtime": {"mode": "local"},
                    "universe": {"symbols": ["au", "rb"]},
                    "router": {"mode": "priority"},
                    "strategies": [{"name": "simple_strategy", "symbols": ["au", "rb"]}],
                },
                "redaction_status": {"redacted": True},
            },
            "artifacts": {},
        },
    )

    runs = list_runs(artifacts_root=artifacts)

    assert len(runs) == 1
    assert runs[0]["runtime_id"] == "rt_local"
    assert runs[0]["router_mode"] == "priority"
    assert runs[0]["universe_symbols"] == ["au", "rb"]
    assert runs[0]["strategy_names"] == ["simple_strategy"]


def test_inspect_run_reports_portfolio_metrics_observation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    rid = "rt_metrics_observation"
    _write_manifest(
        tmp_path,
        rid,
        {
            "runtime": {"mode": "local"},
            "universe": {"symbols": ["au"]},
            "strategies": [{"name": "simple_strategy", "symbols": ["au"]}],
        },
    )
    store = tmp_path / "data" / "store" / "local" / rid
    _append_jsonl(
        store / "metrics.jsonl",
        {
            "envelope": {
                "schema_version": "1",
                "event_id": "metrics-1",
                "event_type": "observation",
                "runtime_id": rid,
                "runtime_profile": "local",
                "datastore_scope": "local",
                "execution_env": "simulated",
                "broker_profile": "simulated",
                "submit_mode": "none",
                "is_live": False,
                "is_simulated_execution": True,
                "generated_at": "2026-05-08T00:00:00+00:00",
                "source": "datastore",
                "payload_type": "observation",
            },
            "payload": {
                "ts": 1,
                "metrics": {
                    "cash": 980000.0,
                    "equity": 1002000.0,
                    "margin_used": 22000.0,
                    "risk_ratio": 0.021956,
                    "max_risk_ratio_seen": 0.03,
                    "unrealized_pnl": 1500.0,
                    "realized_pnl": 500.0,
                    "notional_by_symbol": {"au": 100000.0},
                    "margin_by_symbol": {"au": 12000.0},
                    "unrealized_pnl_by_symbol": {"au": 1500.0},
                    "source": "runtime_observation",
                    "state_source_of_truth": False,
                },
            },
        },
    )

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "data" / "store",
        artifacts_root=tmp_path / "data" / "artifacts",
        tail=30,
    )

    portfolio = report["dashboard_projection"]["portfolio"]["local"]
    assert portfolio["equity"] == 1002000.0
    assert portfolio["cash"] == 980000.0
    assert portfolio["margin_used"] == 22000.0
    assert portfolio["risk_ratio"] == 0.021956
    assert portfolio["margin_by_symbol"] == {"au": 12000.0}


def test_inspect_run_uses_manifest_trading_sessions_for_dryrun_and_live(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    for mode in ("dryrun", "live"):
        rid = f"rt_{mode}"
        _write_manifest(
            tmp_path,
            rid,
            {
                "runtime": {"mode": mode},
                "universe": {"symbols": ["au"]},
                "instruments": {
                    "trading_sessions": {
                        "au": [
                            {"start": "09:00", "end": "10:15"},
                            {"start": "21:00", "end": "02:30"},
                        ]
                    },
                    "roll_policy": {"contracts": {"au": "SHFE.au2606"}},
                },
                "strategies": [{"name": "simple_strategy", "symbols": ["au"]}],
            },
        )
        _append_jsonl(
            tmp_path / "data" / "store" / mode / rid / "order_events.jsonl",
            {
                "event_type": "order",
                "event_id": f"{mode}-order",
                "runtime_id": rid,
                "runtime_profile": mode,
                "datastore_scope": mode,
                "source": "runtime",
                "payload_type": "order_event",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2606",
                "market_price": 450.0,
                "ts": _ts("2026-05-08T20:30:00"),
            },
        )

        report = inspect_run(
            runtime_id=rid,
            store_root=tmp_path / "data" / "store",
            artifacts_root=tmp_path / "data" / "artifacts",
            tail=30,
        )

        quote = report["dashboard_projection"]["quotes"][mode]["by_symbol"]["au"]
        assert quote["available"] is True
        assert quote["tradability"]["state"] == "non_trading_time"
        assert quote["tradability"]["source"] == "trading_sessions"


def test_inspect_run_uses_manifest_trade_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    rid = "rt_local_contracts"
    _write_manifest(
        tmp_path,
        rid,
        {
            "runtime": {"mode": "local"},
            "universe": {"symbols": ["au", "rb"]},
            "instruments": {
                "roll_policy": {
                    "contracts": {"au": "SHFE.au2606", "rb": "SHFE.rb2610"}
                }
            },
            "strategies": [{"name": "simple_strategy", "symbols": ["au", "rb"]}],
        },
    )

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "data" / "store",
        artifacts_root=tmp_path / "data" / "artifacts",
        tail=30,
    )

    quotes = report["dashboard_projection"]["quotes"]["local"]
    assert quotes["by_symbol"]["au"]["trade_instrument_id"] == "SHFE.au2606"
    assert quotes["by_symbol"]["rb"]["trade_instrument_id"] == "SHFE.rb2610"
    assert "SHFE.au2606" in quotes["by_contract"]
    assert "SHFE.rb2610" in quotes["by_contract"]
