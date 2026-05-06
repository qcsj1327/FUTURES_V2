from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

AuditSeverity = Literal["info", "warning", "critical"]
AuditStatus = Literal["ok", "degraded", "not_ready"]
AuditArtifactType = Literal[
    "live_audit_observation",
    "live_audit_report",
    "runtime_diagnostics",
]
ReadinessStatus = Literal["ready", "degraded", "not_ready"]

CANONICAL_AUDIT_SCOPES = {"local", "dryrun", "live"}


@dataclass(frozen=True)
class AuditThresholds:
    cash_delta_warning: float = 1.0
    cash_delta_critical: float = 100.0
    equity_delta_warning: float = 1.0
    equity_delta_critical: float = 100.0
    margin_used_delta_warning: float = 1.0
    margin_used_delta_critical: float = 100.0
    position_qty_delta_warning: float = 0.0
    position_qty_delta_critical: float = 1.0
    stale_after_seconds: int = 600


@dataclass(frozen=True)
class AuditObservation:
    code: str
    message: str
    severity: AuditSeverity
    runtime_id: str
    runtime_profile: str
    datastore_scope: str
    is_live: bool
    generated_at: str
    is_source_of_truth: bool = False
    mutation_allowed: bool = False
    diagnostic_only: bool = True
    values: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuditAlert:
    code: str
    message: str
    severity: AuditSeverity
    runtime_id: str
    runtime_profile: str
    datastore_scope: str
    is_live: bool
    generated_at: str
    suggested_action: str | None = None
    is_source_of_truth: bool = False
    mutation_allowed: bool = False
    diagnostic_only: bool = True
    source: str = "audit_artifact"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AuditReport:
    schema_version: str
    artifact_type: AuditArtifactType
    runtime_id: str
    runtime_profile: str
    datastore_scope: str
    is_live: bool
    generated_at: str
    is_source_of_truth: bool = False
    mutation_allowed: bool = False
    diagnostic_only: bool = True
    observations: list[AuditObservation] = field(default_factory=list)
    alerts: list[AuditAlert] = field(default_factory=list)
    diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "artifact_type": self.artifact_type,
            "runtime_id": self.runtime_id,
            "runtime_profile": self.runtime_profile,
            "datastore_scope": self.datastore_scope,
            "is_live": self.is_live,
            "generated_at": self.generated_at,
            "is_source_of_truth": self.is_source_of_truth,
            "mutation_allowed": self.mutation_allowed,
            "diagnostic_only": self.diagnostic_only,
            "observations": [item.to_dict() for item in self.observations],
            "alerts": [item.to_dict() for item in self.alerts],
            "diagnostics": list(self.diagnostics),
        }


@dataclass(frozen=True)
class ReadinessReport:
    schema_version: str
    artifact_type: Literal["readiness_report"]
    runtime_id: str
    runtime_profile: str
    datastore_scope: str
    is_live: bool
    generated_at: str
    status: ReadinessStatus
    checks: dict[str, str]
    diagnostics: list[str] = field(default_factory=list)
    is_source_of_truth: bool = False
    mutation_allowed: bool = False
    diagnostic_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
