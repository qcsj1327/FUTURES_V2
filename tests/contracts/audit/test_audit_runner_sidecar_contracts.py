from __future__ import annotations

import inspect
import json
from pathlib import Path

from app.orchestration import audit_runner
from app.orchestration.audit_runner import run_audit_sidecar


class _Position:
    instrument_id = "au"
    quantity = 1.0


class _Portfolio:
    metadata = {"cash": 1000.0, "equity": 1000.0, "margin_used": 10.0}
    positions = {"au": _Position()}


def test_audit_runner_does_not_use_state_or_trading_event_apis() -> None:
    source = inspect.getsource(audit_runner)

    assert "StateEngine" not in source
    assert "apply_order_event" not in source
    assert "apply_fill_event" not in source
    assert "OrderEvent(" not in source
    assert "FillEvent(" not in source
    assert "append_order_event" not in source
    assert "append_fill_event" not in source
    assert "append_order_lifecycle_event" not in source
    assert "save_portfolio_snapshot" not in source


def test_audit_runner_writes_scoped_audit_and_readiness_artifacts(tmp_path: Path) -> None:
    result = run_audit_sidecar(
        runtime_id="rt_live",
        runtime_profile="live",
        datastore_scope="live",
        portfolio_snapshot=_Portfolio(),
        broker_snapshot_provider=lambda: {
            "cash": 1000.0,
            "equity": 1000.0,
            "margin_used": 10.0,
            "positions_qty_by_symbol": {"au": 1.0},
        },
        artifacts_root=tmp_path / "data" / "artifacts",
        store_scope="live",
        artifact_scope="live",
    )

    assert result.audit_path is not None
    assert result.readiness_path is not None
    assert result.audit_path.parent == tmp_path / "data" / "artifacts" / "live" / "audit"
    assert result.readiness_path.parent == tmp_path / "data" / "artifacts" / "live" / "audit"
    audit_payload = json.loads(result.audit_path.read_text(encoding="utf-8"))
    assert audit_payload["artifact_type"] == "live_audit_observation"
    assert audit_payload["runtime_profile"] == "live"
    assert audit_payload["datastore_scope"] == "live"
    assert audit_payload["is_live"] is True
    assert result.execution_action is None
    assert result.risk_action is None
    assert result.state_action is None
    assert result.mutation_allowed is False


def test_audit_runner_failure_writes_degraded_readiness_without_state_action(
    tmp_path: Path,
) -> None:
    def _broken_provider() -> dict[str, object]:
        raise RuntimeError("broker unavailable")

    result = run_audit_sidecar(
        runtime_id="rt_live",
        runtime_profile="live",
        datastore_scope="live",
        portfolio_snapshot=_Portfolio(),
        broker_snapshot_provider=_broken_provider,
        artifacts_root=tmp_path / "data" / "artifacts",
        store_scope="live",
        artifact_scope="live",
    )

    assert result.audit_path is None
    assert result.readiness_path is not None
    payload = json.loads(result.readiness_path.read_text(encoding="utf-8"))
    assert payload["status"] == "degraded"
    assert payload["mutation_allowed"] is False
    assert result.state_action is None


def test_local_and_dryrun_sidecar_are_diagnostics_only(tmp_path: Path) -> None:
    for scope in ("local", "dryrun"):
        result = run_audit_sidecar(
            runtime_id=f"rt_{scope}",
            runtime_profile=scope,
            datastore_scope=scope,
            portfolio_snapshot=_Portfolio(),
            broker_snapshot_provider=lambda: {},
            artifacts_root=tmp_path / "data" / "artifacts",
            store_scope=scope,
            artifact_scope=scope,
        )

        assert result.audit_path is not None
        payload = json.loads(result.audit_path.read_text(encoding="utf-8"))
        assert payload["artifact_type"] == "runtime_diagnostics"
        assert payload["diagnostic_only"] is True
        assert payload["is_live"] is False
        assert "reconciliation" not in str(payload).lower()


def test_live_sidecar_keeps_critical_alert_as_suggested_action_only(tmp_path: Path) -> None:
    result = run_audit_sidecar(
        runtime_id="rt_live",
        runtime_profile="live",
        datastore_scope="live",
        portfolio_snapshot=_Portfolio(),
        broker_snapshot_provider=lambda: {
            "cash": 0.0,
            "equity": 0.0,
            "margin_used": 10.0,
            "positions_qty_by_symbol": {"au": 9.0},
        },
        artifacts_root=tmp_path / "data" / "artifacts",
        store_scope="live",
        artifact_scope="live",
    )

    assert result.audit_report is not None
    assert result.audit_report.alerts
    assert {alert.suggested_action for alert in result.audit_report.alerts} == {
        "suspend_new_trading"
    }
    assert result.execution_action is None
    assert result.risk_action is None
    assert result.state_action is None
