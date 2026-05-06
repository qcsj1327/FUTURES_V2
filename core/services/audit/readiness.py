from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from core.services.audit.contracts import (
    CANONICAL_AUDIT_SCOPES,
    ReadinessReport,
    ReadinessStatus,
)


class ReadinessChecker:
    def check(
        self,
        *,
        runtime_id: str,
        runtime_profile: str,
        datastore_scope: str,
        broker_snapshot_provider: Callable[[], object] | None = None,
        store_scope: str | None = None,
        artifact_scope: str | None = None,
        latest_audit_generated_at: str | None = None,
        stale_after_seconds: int = 600,
        generated_at: str | None = None,
    ) -> ReadinessReport:
        now = generated_at or _now_iso()
        checks: dict[str, str] = {}
        diagnostics: list[str] = []

        if (
            runtime_profile not in CANONICAL_AUDIT_SCOPES
            or datastore_scope not in CANONICAL_AUDIT_SCOPES
        ):
            checks["scope"] = "not_ready"
            diagnostics.append("invalid_scope")
        elif runtime_profile != datastore_scope:
            checks["scope"] = "not_ready"
            diagnostics.append("runtime_profile_datastore_scope_mismatch")
        else:
            checks["scope"] = "ready"

        if broker_snapshot_provider is None:
            checks["broker_snapshot_capability"] = "degraded"
            diagnostics.append("missing_broker_snapshot_capability")
        else:
            checks["broker_snapshot_capability"] = "ready"

        if store_scope is not None and store_scope != datastore_scope:
            checks["store_scope"] = "not_ready"
            diagnostics.append("store_scope_mismatch")
        elif store_scope is not None:
            checks["store_scope"] = "ready"

        if artifact_scope is not None and artifact_scope != datastore_scope:
            checks["artifact_scope"] = "not_ready"
            diagnostics.append("artifact_scope_mismatch")
        elif artifact_scope is not None:
            checks["artifact_scope"] = "ready"

        if _is_stale(latest_audit_generated_at, now, stale_after_seconds):
            checks["audit_freshness"] = "degraded"
            diagnostics.append("stale_audit_observation")
        elif latest_audit_generated_at is not None:
            checks["audit_freshness"] = "ready"

        status = _overall_status(checks)
        return ReadinessReport(
            schema_version="1",
            artifact_type="readiness_report",
            runtime_id=runtime_id,
            runtime_profile=runtime_profile,
            datastore_scope=datastore_scope,
            is_live=runtime_profile == "live" and datastore_scope == "live",
            generated_at=now,
            status=status,
            checks=checks,
            diagnostics=diagnostics,
        )


def latest_audit_generated_at(path: Path) -> str | None:
    if not path.exists():
        return None
    latest: str | None = None
    for item in sorted(path.glob("audit_*.json")):
        latest = item.stem.rsplit("_", 1)[-1]
    return latest


def _overall_status(checks: dict[str, str]) -> ReadinessStatus:
    if any(value == "not_ready" for value in checks.values()):
        return "not_ready"
    if any(value == "degraded" for value in checks.values()):
        return "degraded"
    return "ready"


def _is_stale(
    latest_generated_at: str | None,
    now: str,
    stale_after_seconds: int,
) -> bool:
    if latest_generated_at is None:
        return False
    latest = _parse_iso(latest_generated_at)
    current = _parse_iso(now)
    if latest is None or current is None:
        return True
    return (current - latest).total_seconds() > stale_after_seconds


def _parse_iso(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()
