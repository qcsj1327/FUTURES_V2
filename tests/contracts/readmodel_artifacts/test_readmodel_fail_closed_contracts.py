from __future__ import annotations

import json
from pathlib import Path

from core.services.runtime.event_codec import encode_datastore_event
from web.readmodel.dashboard import inspect_run
from web.readmodel.dashboard_projection import build_dashboard_projection


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _manifest(
    *,
    runtime_id: str,
    scope: str | None,
    plan: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "kind": "promotion_manifest",
        "runtime_id": runtime_id,
        "created_at": "2026-05-08T00:00:00+00:00",
        "candidate_id": "cand",
        "status": "running",
        "plan": {
            "path": "plan.json",
            "sha256": "sha",
            "effective_config_summary": plan or {"runtime": {"mode": scope}},
            "redaction_status": {"redacted": True},
        },
        "artifacts": {},
    }
    if scope is not None:
        payload.update(
            {"runtime_profile": scope, "datastore_scope": scope, "is_live": scope == "live"}
        )
    return payload


def test_manifest_missing_scope_fails_closed_not_live(tmp_path: Path) -> None:
    rid = "rt_missing_scope"
    _write_json(
        tmp_path / "artifacts" / "manifests" / f"manifest_{rid}_20260508T000000Z.json",
        _manifest(runtime_id=rid, scope=None, plan={"runtime": {"mode": "live"}}),
    )

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "store",
        artifacts_root=tmp_path / "artifacts",
    )

    assert report["fail_closed"] is True
    assert report["dashboard_projection"]["execution_state"]["runtime_profile"] is None
    assert report["dashboard_projection"]["positions"]["live"]["items"] == []


def test_illegal_runtime_mode_fails_closed_not_live(tmp_path: Path) -> None:
    rid = "rt_bad_mode"
    _write_json(
        tmp_path / "artifacts" / "manifests" / f"manifest_{rid}_20260508T000000Z.json",
        _manifest(runtime_id=rid, scope="live", plan={"runtime": {"mode": "bad"}}),
    )

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "store",
        artifacts_root=tmp_path / "artifacts",
    )

    assert report["fail_closed"] is True
    assert "runtime_mode_mismatch" in report["fail_closed_reasons"][0]


def test_legacy_flat_row_does_not_enter_live_truth() -> None:
    legacy = {
        "order_id": "legacy",
        "symbol": "au",
        "trade_instrument_id": "SHFE.au2606",
        "status": "SUBMITTED",
        "quantity": 1.0,
        "market_price": 450.0,
        "ts": 1,
    }
    projection = build_dashboard_projection(
        runtime_id="rt_projection",
        plan_cfg={"runtime": {"mode": "live"}, "universe": {"symbols": ["au"]}},
        execution={},
        portfolio={"local": None, "dryrun": None, "live": {}},
        latest_portfolios={"local": None, "dryrun": None, "live": None},
        event_stats={"local": {}, "dryrun": {}, "live": {}},
        lifecycle_events={"local": [], "dryrun": [], "live": [legacy]},
        order_events={"local": [], "dryrun": [], "live": [legacy]},
        fill_events={"local": [], "dryrun": [], "live": [legacy]},
        rank_events={"local": [], "dryrun": [], "live": []},
        strategy_score_events={"local": [], "dryrun": [], "live": []},
        lifecycle_stats={"local": {}, "dryrun": {}, "live": {}},
        risk_stats={"local": {}, "dryrun": {}, "live": {}},
        top_lifecycle_reject_reasons={"local": [], "dryrun": [], "live": []},
        strategy_switch_proposal=None,
        strategy_switch_approved=None,
        strategy_switch_rejected=None,
        enabled_strategies_by_symbol={"local": {}, "dryrun": {}, "live": {}},
        warning_codes=[],
    )

    assert projection["pending_orders"]["live"]["items"] == []
    assert projection["quotes"]["live"]["by_symbol"]["au"]["available"] is False
    assert projection["positions"]["live"]["items"] == []


def test_old_runtime_id_is_not_current_live_run(tmp_path: Path) -> None:
    rid = "rt_livefile"
    live_store = tmp_path / "store" / "live" / rid
    (live_store / "order_events.jsonl").parent.mkdir(parents=True)
    (live_store / "order_events.jsonl").write_text(
        json.dumps({"order_id": "legacy-flat", "runtime_id": rid}) + "\n",
        encoding="utf-8",
    )

    report = inspect_run(
        runtime_id=rid,
        store_root=tmp_path / "store",
        artifacts_root=tmp_path / "artifacts",
    )

    assert report["fail_closed"] is True
    assert report["event_stats"]["live"]["order_events_lines"] == 0


def test_valid_enveloped_row_survives_scope_filter(tmp_path: Path) -> None:
    event = encode_datastore_event(
        base={
            "ts": 1,
            "runtime_id": "rt_valid",
            "scope": "live",
            "symbol": "au",
            "strategy_name": "contract",
            "strategy_impl": "contract",
        },
        event_type="order_lifecycle",
        payload_type="order_lifecycle",
        source="contract",
        payload={"order_id": "ok", "status": "SUBMITTED", "quantity": 1.0, "ts": 1},
    )
    _write_json(
        tmp_path / "artifacts" / "manifests" / "manifest_rt_valid_20260508T000000Z.json",
        _manifest(runtime_id="rt_valid", scope="live", plan={"runtime": {"mode": "live"}}),
    )
    path = tmp_path / "store" / "live" / "rt_valid" / "order_lifecycle_events.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(event) + "\n", encoding="utf-8")

    report = inspect_run(
        runtime_id="rt_valid",
        store_root=tmp_path / "store",
        artifacts_root=tmp_path / "artifacts",
    )

    assert report["pending_orders_count"]["live"] == 1
