from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.services.audit.artifacts import write_audit_report, write_readiness_report
from core.services.audit.readiness import ReadinessChecker
from core.services.audit.service import AuditService


def test_audit_artifact_path_and_required_scope_fields(tmp_path: Path) -> None:
    report = AuditService().collect(
        runtime_id="rt_live",
        runtime_profile="live",
        datastore_scope="live",
        portfolio_snapshot=None,
        broker_snapshot=None,
        generated_at="2026-05-09T00:00:00+00:00",
    )

    path = write_audit_report(report, artifacts_root=tmp_path / "data" / "artifacts")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert path.parent == tmp_path / "data" / "artifacts" / "live" / "audit"
    assert payload["schema_version"] == "1"
    assert payload["runtime_profile"] == "live"
    assert payload["datastore_scope"] == "live"
    assert payload["is_live"] is True
    assert payload["generated_at"]


def test_audit_artifact_redacts_sensitive_keys(tmp_path: Path) -> None:
    report = AuditService().collect(
        runtime_id="rt_live",
        runtime_profile="live",
        datastore_scope="live",
        portfolio_snapshot=None,
        broker_snapshot=None,
        generated_at="2026-05-09T00:00:00+00:00",
    )
    payload = report.to_dict()
    payload["diagnostics"] = [
        {
            "token": "plain-token",
            "password": "plain-password",
            "secret": "plain-secret",
            "credential": "plain-credential",
            "env": "BROKER_PASSWORD=plain",
        }
    ]

    path = write_audit_report(payload, artifacts_root=tmp_path / "data" / "artifacts")
    text = path.read_text(encoding="utf-8")

    assert "plain-token" not in text
    assert "plain-password" not in text
    assert "plain-secret" not in text
    assert "plain-credential" not in text
    assert "BROKER_PASSWORD=plain" not in text


def test_local_dryrun_artifact_cannot_be_written_as_live(tmp_path: Path) -> None:
    report = AuditService().collect(
        runtime_id="rt_local",
        runtime_profile="local",
        datastore_scope="local",
        portfolio_snapshot=None,
        broker_snapshot=None,
        generated_at="2026-05-09T00:00:00+00:00",
    ).to_dict()
    report["datastore_scope"] = "live"

    with pytest.raises(ValueError, match="runtime_profile/datastore_scope mismatch"):
        write_audit_report(report, artifacts_root=tmp_path / "data" / "artifacts")


def test_readiness_artifact_uses_scoped_audit_path(tmp_path: Path) -> None:
    report = ReadinessChecker().check(
        runtime_id="rt_live",
        runtime_profile="live",
        datastore_scope="live",
        broker_snapshot_provider=lambda: {},
        generated_at="2026-05-09T00:00:00+00:00",
    )

    path = write_readiness_report(report, artifacts_root=tmp_path / "data" / "artifacts")

    assert path.parent == tmp_path / "data" / "artifacts" / "live" / "audit"
    assert path.name.startswith("readiness_rt_live_")
