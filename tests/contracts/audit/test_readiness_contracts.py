from __future__ import annotations

from core.services.audit.readiness import ReadinessChecker


def test_readiness_status_vocab_only() -> None:
    report = ReadinessChecker().check(
        runtime_id="rt_live",
        runtime_profile="live",
        datastore_scope="live",
        broker_snapshot_provider=lambda: {},
        generated_at="2026-05-09T00:00:00+00:00",
    )

    assert report.status in {"ready", "degraded", "not_ready"}
    payload = report.to_dict()
    forbidden = {"order_event", "fill_event", "position_mutation", "pnl_mutation"}
    assert forbidden.isdisjoint(payload)
    assert payload["is_source_of_truth"] is False
    assert payload["mutation_allowed"] is False


def test_missing_broker_capability_degrades_readiness() -> None:
    report = ReadinessChecker().check(
        runtime_id="rt_live",
        runtime_profile="live",
        datastore_scope="live",
        broker_snapshot_provider=None,
        generated_at="2026-05-09T00:00:00+00:00",
    )

    assert report.status in {"degraded", "not_ready"}
    assert "missing_broker_snapshot_capability" in report.diagnostics


def test_invalid_scope_is_not_ready() -> None:
    report = ReadinessChecker().check(
        runtime_id="rt_bad",
        runtime_profile="bad",
        datastore_scope="live",
        broker_snapshot_provider=lambda: {},
        generated_at="2026-05-09T00:00:00+00:00",
    )

    assert report.status == "not_ready"
    assert "invalid_scope" in report.diagnostics


def test_stale_audit_observation_degrades_readiness() -> None:
    report = ReadinessChecker().check(
        runtime_id="rt_live",
        runtime_profile="live",
        datastore_scope="live",
        broker_snapshot_provider=lambda: {},
        latest_audit_generated_at="2026-05-09T00:00:00+00:00",
        generated_at="2026-05-09T00:30:00+00:00",
        stale_after_seconds=60,
    )

    assert report.status == "degraded"
    assert "stale_audit_observation" in report.diagnostics
