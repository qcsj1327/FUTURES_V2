from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from config.instrument_universe import default_symbols
from core.execution.lifecycle_reasons import BLOCKED_BY_PENDING_ORDER
from core.services.runtime.event_codec import encode_datastore_event
from web.readmodel.dashboard import inspect_run


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if "envelope" not in payload:
        scope = path.parts[-3]
        runtime_id = path.parts[-2]
        payload = encode_datastore_event(
            base={
                "ts": int(payload.get("ts", 0) or 0),
                "runtime_id": runtime_id,
                "scope": scope,
                "symbol": str(payload.get("symbol") or payload.get("instrument_id") or ""),
                "strategy_name": "contract",
                "strategy_impl": "contract",
            },
            event_type="order_lifecycle",
            payload_type="order_lifecycle",
            source="contract",
            payload=payload,
        )
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _write_manifest(root: Path, runtime_id: str, plan_cfg: dict[str, Any]) -> None:
    artifacts = root / "data" / "artifacts"
    _write_json(
        artifacts / "manifests" / f"manifest_{runtime_id}_20260508T000000Z.json",
        {
            "kind": "promotion_manifest",
            "runtime_id": runtime_id,
            "created_at": "2026-05-08T00:00:00+00:00",
            "candidate_id": "cand_test",
            "runtime_profile": "live",
            "datastore_scope": "live",
            "is_live": True,
            "status": "running",
            "plan": {
                "path": "plan.json",
                "sha256": "sha",
                "effective_config_summary": plan_cfg,
                "redaction_status": {"redacted": True},
            },
            "artifacts": {
                "current_summary": str(artifacts / "summaries" / f"current_{runtime_id}.json"),
                "candidate_summary": None,
                "decision": None,
                "approved": None,
                "strategy_switch_proposal": None,
                "strategy_switch_approved": None,
            },
        },
    )
    _write_json(
        artifacts / "summaries" / f"current_{runtime_id}.json",
        {"kind": "summary", "runtime_id": runtime_id, "status": "running"},
    )


def test_inspect_pending_reports_count_and_reject_reasons(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    runtime_id = "rt_inspect"
    symbols = default_symbols()
    _write_manifest(
        tmp_path,
        runtime_id,
        {
            "runtime": {"mode": "live", "default_quantity": 1.0},
            "universe": {"symbols": symbols},
            "instruments": {
                "roll_policy": {
                    "contracts": {symbol: f"SHFE.{symbol}2606" for symbol in symbols},
                },
            },
        },
    )
    lifecycle_path = (
        tmp_path
        / "data"
        / "store"
        / "live"
        / runtime_id
        / "order_lifecycle_events.jsonl"
    )
    for idx, symbol in enumerate(symbols):
        _append_jsonl(
            lifecycle_path,
            {
                "event_type": "order_lifecycle",
                "runtime_id": runtime_id,
                "runtime_profile": "live",
                "datastore_scope": "live",
                "order_id": f"order_{idx}",
                "symbol": symbol,
                "trade_instrument_id": f"SHFE.{symbol}2606",
                "status": "SUBMITTED",
                "reason": "order_submitted",
                "quantity": 1.0,
                "ts": idx,
            },
        )
    _append_jsonl(
        lifecycle_path,
        {
            "event_type": "order_lifecycle",
            "runtime_id": runtime_id,
            "runtime_profile": "live",
            "datastore_scope": "live",
            "order_id": "blocked_1",
            "symbol": symbols[0],
            "trade_instrument_id": f"SHFE.{symbols[0]}2606",
            "status": "REJECTED",
            "reason": BLOCKED_BY_PENDING_ORDER,
            "quantity": 1.0,
            "ts": len(symbols) + 1,
        },
    )

    report = inspect_run(
        runtime_id=runtime_id,
        store_root=tmp_path / "data" / "store",
        artifacts_root=tmp_path / "data" / "artifacts",
        tail=50,
    )

    assert "missing_candidate_summary" not in report["warnings"]
    assert "missing_strategy_switch_approved" in report["optional_warnings"]
    assert report["pending_orders_count"]["live"] == len(symbols)
    projection_pending = report["dashboard_projection"]["pending_orders"]["live"]
    assert projection_pending["count"] == len(symbols)
    assert projection_pending["items"][0]["status"] in {"NEW", "SUBMITTED", "PARTIAL"}
    assert report["dashboard_projection"]["positions"]["live"]["items"] == []
    reasons = {item["reason"] for item in report["top_lifecycle_reject_reasons"]["live"]}
    assert BLOCKED_BY_PENDING_ORDER in reasons
