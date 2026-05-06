from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.services.audit.artifacts import write_audit_report, write_readiness_report
from core.services.audit.contracts import AuditReport, AuditThresholds, ReadinessReport
from core.services.audit.readiness import ReadinessChecker
from core.services.audit.service import AuditService

BrokerSnapshotProvider = Callable[[], Mapping[str, Any] | None]


@dataclass(frozen=True)
class AuditSidecarResult:
    audit_report: AuditReport | None
    readiness_report: ReadinessReport
    audit_path: Path | None
    readiness_path: Path | None
    warnings: list[str]

    @property
    def mutation_allowed(self) -> bool:
        return False

    @property
    def execution_action(self) -> None:
        return None

    @property
    def risk_action(self) -> None:
        return None

    @property
    def state_action(self) -> None:
        return None


def run_audit_sidecar(
    *,
    runtime_id: str,
    runtime_profile: str,
    datastore_scope: str,
    portfolio_snapshot: Any | None,
    broker_snapshot_provider: BrokerSnapshotProvider | None,
    artifacts_root: Path,
    thresholds: AuditThresholds | None = None,
    store_scope: str | None = None,
    artifact_scope: str | None = None,
) -> AuditSidecarResult:
    try:
        report = AuditService(thresholds=thresholds).collect(
            runtime_id=runtime_id,
            runtime_profile=runtime_profile,
            datastore_scope=datastore_scope,
            portfolio_snapshot=portfolio_snapshot,
            broker_snapshot_provider=broker_snapshot_provider,
        )
        readiness = ReadinessChecker().check(
            runtime_id=runtime_id,
            runtime_profile=runtime_profile,
            datastore_scope=datastore_scope,
            broker_snapshot_provider=broker_snapshot_provider,
            store_scope=store_scope,
            artifact_scope=artifact_scope,
            stale_after_seconds=(thresholds or AuditThresholds()).stale_after_seconds,
        )
        audit_path = write_audit_report(report, artifacts_root=artifacts_root)
        readiness_path = write_readiness_report(readiness, artifacts_root=artifacts_root)
        return AuditSidecarResult(
            audit_report=report,
            readiness_report=readiness,
            audit_path=audit_path,
            readiness_path=readiness_path,
            warnings=[],
        )
    except Exception as exc:
        readiness = _sidecar_failure_readiness(
            runtime_id=runtime_id,
            runtime_profile=runtime_profile,
            datastore_scope=datastore_scope,
            reason=exc.__class__.__name__,
        )
        readiness_path = write_readiness_report(readiness, artifacts_root=artifacts_root)
        return AuditSidecarResult(
            audit_report=None,
            readiness_report=readiness,
            audit_path=None,
            readiness_path=readiness_path,
            warnings=[f"audit_sidecar_failed:{exc.__class__.__name__}"],
        )


def broker_snapshot_provider_from_universe(universe_runtime: Any) -> BrokerSnapshotProvider | None:
    broker = _broker_from_universe(universe_runtime)
    snapshot_fn = getattr(broker, "portfolio_snapshot", None)
    if not callable(snapshot_fn):
        return None

    def _provider() -> Mapping[str, Any] | None:
        snapshot = snapshot_fn()
        if isinstance(snapshot, Mapping):
            return snapshot
        return None

    return _provider


def portfolio_snapshot_from_universe(universe_runtime: Any) -> Any | None:
    executor = getattr(universe_runtime, "executor", None)
    state = getattr(executor, "state", None)
    return getattr(state, "portfolio", None)


def _broker_from_universe(universe_runtime: Any) -> Any | None:
    executor = getattr(universe_runtime, "executor", None)
    execution = getattr(executor, "execution", None)
    return getattr(execution, "broker", None)


def _sidecar_failure_readiness(
    *,
    runtime_id: str,
    runtime_profile: str,
    datastore_scope: str,
    reason: str,
) -> ReadinessReport:
    return ReadinessReport(
        schema_version="1",
        artifact_type="readiness_report",
        runtime_id=runtime_id,
        runtime_profile=runtime_profile,
        datastore_scope=datastore_scope,
        is_live=runtime_profile == "live" and datastore_scope == "live",
        status="degraded",
        checks={"audit_sidecar": "degraded"},
        diagnostics=[f"audit_sidecar_failed:{reason}"],
        generated_at=datetime.now(UTC).replace(microsecond=0).isoformat(),
    )
