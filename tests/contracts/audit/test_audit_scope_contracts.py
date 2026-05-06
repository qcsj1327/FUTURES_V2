from __future__ import annotations

from core.services.audit.service import AuditService


def test_live_audit_scope_fields() -> None:
    report = AuditService().collect(
        runtime_id="rt_live",
        runtime_profile="live",
        datastore_scope="live",
        portfolio_snapshot=None,
        broker_snapshot=None,
        generated_at="2026-05-09T00:00:00+00:00",
    ).to_dict()

    assert report["artifact_type"] in {"live_audit_observation", "live_audit_report"}
    assert report["runtime_profile"] == "live"
    assert report["datastore_scope"] == "live"
    assert report["is_live"] is True
    assert report["diagnostic_only"] is False


def test_local_and_dryrun_are_diagnostics_only_without_reconciliation_name() -> None:
    for scope in ("local", "dryrun"):
        report = AuditService().collect(
            runtime_id=f"rt_{scope}",
            runtime_profile=scope,
            datastore_scope=scope,
            portfolio_snapshot=None,
            broker_snapshot=None,
            generated_at="2026-05-09T00:00:00+00:00",
        ).to_dict()

        assert report["artifact_type"] == "runtime_diagnostics"
        assert report["diagnostic_only"] is True
        assert report["is_live"] is False
        assert "reconciliation" not in str(report).lower()


def test_scope_mismatch_is_diagnostics_only_not_live() -> None:
    report = AuditService().collect(
        runtime_id="rt_bad",
        runtime_profile="dryrun",
        datastore_scope="live",
        portfolio_snapshot=None,
        broker_snapshot=None,
        generated_at="2026-05-09T00:00:00+00:00",
    ).to_dict()

    assert report["artifact_type"] == "runtime_diagnostics"
    assert report["is_live"] is False
    assert report["diagnostic_only"] is True
    assert "invalid_scope" in report["diagnostics"]
