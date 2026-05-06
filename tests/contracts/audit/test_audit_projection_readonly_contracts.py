from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

from core.services.audit.artifacts import write_audit_report
from core.services.audit.service import AuditService
from web.readmodel import audit as audit_readmodel
from web.readmodel.audit import load_audit_projection
from web.readmodel.dashboard_projection import build_dashboard_projection


def test_audit_readmodel_reads_artifacts_only() -> None:
    source = inspect.getsource(audit_readmodel)

    assert "append_order_event" not in source
    assert "append_fill_event" not in source
    assert "save_portfolio_snapshot" not in source
    assert "StateEngine" not in source
    assert "OrderEvent(" not in source
    assert "FillEvent(" not in source


def test_audit_reader_does_not_read_local_or_dryrun_as_live(tmp_path: Path) -> None:
    report = AuditService().collect(
        runtime_id="rt_shared",
        runtime_profile="dryrun",
        datastore_scope="dryrun",
        portfolio_snapshot=None,
        broker_snapshot=None,
        generated_at="2026-05-09T00:00:00+00:00",
    )
    write_audit_report(report, artifacts_root=tmp_path / "data" / "artifacts")

    projection = load_audit_projection(
        runtime_id="rt_shared",
        scope="live",
        artifacts_root=tmp_path / "data" / "artifacts",
    )

    assert projection["audit"] is None
    assert projection["alerts"] == []


def test_audit_alerts_merge_with_audit_artifact_source() -> None:
    audit_projection = {
        "diagnostic_only": False,
        "audit": {
            "observations": [
                {
                    "code": "positions_qty_by_symbol_delta",
                    "values": {"symbol": "au", "delta": 2.0},
                }
            ]
        },
        "readiness": None,
        "alerts": [
            {
                "code": "positions_qty_by_symbol_delta",
                "level": "error",
                "message": "critical position quantity audit delta",
            }
        ],
    }

    projection = _projection(audit_projection=audit_projection)

    assert projection["alerts"]["items"][-1]["source"] == "audit_artifact"
    assert projection["alerts"]["items"][-1]["mutation_allowed"] is False
    assert projection["audit"]["is_source_of_truth"] is False


def test_audit_observation_does_not_enter_positions() -> None:
    projection = _projection(
        audit_projection={
            "diagnostic_only": False,
            "audit": {
                "observations": [
                    {
                        "code": "positions_qty_by_symbol_delta",
                        "values": {"symbol": "au", "portfolio_quantity": 1.0},
                    }
                ],
            },
            "alerts": [],
            "readiness": None,
        }
    )

    assert projection["positions"]["live"]["items"] == []
    assert "orders" not in projection["audit"]
    assert "fills" not in projection["audit"]
    assert "pnl" not in projection["audit"]


def _projection(*, audit_projection: dict[str, Any] | None = None) -> dict[str, Any]:
    empty: dict[str, list[dict[str, Any]]] = {"local": [], "dryrun": [], "live": []}
    return build_dashboard_projection(
        runtime_id="rt_live",
        plan_cfg={"runtime": {"mode": "live"}},
        execution={},
        portfolio={"local": None, "dryrun": None, "live": None},
        latest_portfolios={"local": None, "dryrun": None, "live": None},
        event_stats={"local": {}, "dryrun": {}, "live": {}},
        lifecycle_events=empty,
        order_events=empty,
        fill_events=empty,
        rank_events=empty,
        strategy_score_events=empty,
        lifecycle_stats={"local": {}, "dryrun": {}, "live": {}},
        risk_stats={"local": {}, "dryrun": {}, "live": {}},
        top_lifecycle_reject_reasons={"local": [], "dryrun": [], "live": []},
        strategy_switch_proposal=None,
        strategy_switch_approved=None,
        strategy_switch_rejected=None,
        enabled_strategies_by_symbol={"local": {}, "dryrun": {}, "live": {}},
        warning_codes=[],
        audit_projection=audit_projection,
    )
