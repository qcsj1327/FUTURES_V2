from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from core.services.audit.contracts import (
    CANONICAL_AUDIT_SCOPES,
    AuditAlert,
    AuditArtifactType,
    AuditObservation,
    AuditReport,
    AuditSeverity,
    AuditThresholds,
)

SnapshotProvider = Callable[[], Mapping[str, Any] | None]


class AuditService:
    def __init__(self, thresholds: AuditThresholds | None = None) -> None:
        self.thresholds = thresholds or AuditThresholds()

    def collect(
        self,
        *,
        runtime_id: str,
        runtime_profile: str,
        datastore_scope: str,
        portfolio_snapshot: Any | None,
        broker_snapshot: Mapping[str, Any] | None = None,
        broker_snapshot_provider: SnapshotProvider | None = None,
        generated_at: str | None = None,
        latest_audit_generated_at: str | None = None,
    ) -> AuditReport:
        now = generated_at or _now_iso()
        if (
            runtime_profile not in CANONICAL_AUDIT_SCOPES
            or datastore_scope not in CANONICAL_AUDIT_SCOPES
        ):
            return self._invalid_scope_report(
                runtime_id=runtime_id,
                runtime_profile=runtime_profile,
                datastore_scope=datastore_scope,
                generated_at=now,
            )
        if runtime_profile != datastore_scope:
            return self._invalid_scope_report(
                runtime_id=runtime_id,
                runtime_profile=runtime_profile,
                datastore_scope=datastore_scope,
                generated_at=now,
            )

        is_live = runtime_profile == "live"
        diagnostic_only = not is_live
        artifact_type: AuditArtifactType = (
            "live_audit_observation" if is_live else "runtime_diagnostics"
        )
        diagnostics: list[str] = []
        observations: list[AuditObservation] = []
        alerts: list[AuditAlert] = []

        broker = broker_snapshot
        if broker is None and broker_snapshot_provider is not None:
            broker = broker_snapshot_provider()
        if broker is not None:
            broker = dict(broker)

        self._observe_missing(
            observations=observations,
            alerts=alerts,
            diagnostics=diagnostics,
            runtime_id=runtime_id,
            runtime_profile=runtime_profile,
            datastore_scope=datastore_scope,
            is_live=is_live,
            diagnostic_only=diagnostic_only,
            generated_at=now,
            portfolio_snapshot=portfolio_snapshot,
            broker_snapshot=broker,
        )
        if portfolio_snapshot is not None and broker is not None:
            self._observe_numeric_delta(
                name="cash",
                warning=self.thresholds.cash_delta_warning,
                critical=self.thresholds.cash_delta_critical,
                portfolio_value=_portfolio_number(portfolio_snapshot, "cash"),
                broker_value=_mapping_number(broker, "cash"),
                observations=observations,
                alerts=alerts,
                runtime_id=runtime_id,
                runtime_profile=runtime_profile,
                datastore_scope=datastore_scope,
                is_live=is_live,
                diagnostic_only=diagnostic_only,
                generated_at=now,
            )
            self._observe_numeric_delta(
                name="equity",
                warning=self.thresholds.equity_delta_warning,
                critical=self.thresholds.equity_delta_critical,
                portfolio_value=_portfolio_number(portfolio_snapshot, "equity"),
                broker_value=_mapping_number(broker, "equity"),
                observations=observations,
                alerts=alerts,
                runtime_id=runtime_id,
                runtime_profile=runtime_profile,
                datastore_scope=datastore_scope,
                is_live=is_live,
                diagnostic_only=diagnostic_only,
                generated_at=now,
            )
            self._observe_numeric_delta(
                name="margin_used",
                warning=self.thresholds.margin_used_delta_warning,
                critical=self.thresholds.margin_used_delta_critical,
                portfolio_value=_portfolio_number(portfolio_snapshot, "margin_used"),
                broker_value=_mapping_number(broker, "margin_used"),
                observations=observations,
                alerts=alerts,
                runtime_id=runtime_id,
                runtime_profile=runtime_profile,
                datastore_scope=datastore_scope,
                is_live=is_live,
                diagnostic_only=diagnostic_only,
                generated_at=now,
            )
            self._observe_position_deltas(
                portfolio_snapshot=portfolio_snapshot,
                broker_snapshot=broker,
                observations=observations,
                alerts=alerts,
                runtime_id=runtime_id,
                runtime_profile=runtime_profile,
                datastore_scope=datastore_scope,
                is_live=is_live,
                diagnostic_only=diagnostic_only,
                generated_at=now,
            )

        if _is_stale(latest_audit_generated_at, now, self.thresholds.stale_after_seconds):
            observations.append(
                _observation(
                    code="stale_audit_observation",
                    message="latest audit observation is stale",
                    severity="warning",
                    runtime_id=runtime_id,
                    runtime_profile=runtime_profile,
                    datastore_scope=datastore_scope,
                    is_live=is_live,
                    diagnostic_only=diagnostic_only,
                    generated_at=now,
                    values={"latest_audit_generated_at": latest_audit_generated_at},
                )
            )

        return AuditReport(
            schema_version="1",
            artifact_type=artifact_type,
            runtime_id=runtime_id,
            runtime_profile=runtime_profile,
            datastore_scope=datastore_scope,
            is_live=is_live,
            generated_at=now,
            diagnostic_only=diagnostic_only,
            observations=observations,
            alerts=alerts,
            diagnostics=diagnostics,
        )

    def _invalid_scope_report(
        self,
        *,
        runtime_id: str,
        runtime_profile: str,
        datastore_scope: str,
        generated_at: str,
    ) -> AuditReport:
        return AuditReport(
            schema_version="1",
            artifact_type="runtime_diagnostics",
            runtime_id=runtime_id,
            runtime_profile=runtime_profile,
            datastore_scope=datastore_scope,
            is_live=False,
            generated_at=generated_at,
            diagnostic_only=True,
            diagnostics=["invalid_scope"],
        )

    def _observe_missing(
        self,
        *,
        observations: list[AuditObservation],
        alerts: list[AuditAlert],
        diagnostics: list[str],
        runtime_id: str,
        runtime_profile: str,
        datastore_scope: str,
        is_live: bool,
        diagnostic_only: bool,
        generated_at: str,
        portfolio_snapshot: Any | None,
        broker_snapshot: Mapping[str, Any] | None,
    ) -> None:
        if portfolio_snapshot is None:
            diagnostics.append("portfolio_snapshot_missing")
            observations.append(
                _observation(
                    code="portfolio_snapshot_missing",
                    message="portfolio snapshot is missing",
                    severity="critical" if is_live else "warning",
                    runtime_id=runtime_id,
                    runtime_profile=runtime_profile,
                    datastore_scope=datastore_scope,
                    is_live=is_live,
                    diagnostic_only=diagnostic_only,
                    generated_at=generated_at,
                )
            )
        if broker_snapshot is None:
            diagnostics.append("broker_snapshot_missing")
            severity: AuditSeverity = "critical" if is_live else "warning"
            observations.append(
                _observation(
                    code="broker_snapshot_missing",
                    message="broker snapshot is missing",
                    severity=severity,
                    runtime_id=runtime_id,
                    runtime_profile=runtime_profile,
                    datastore_scope=datastore_scope,
                    is_live=is_live,
                    diagnostic_only=diagnostic_only,
                    generated_at=generated_at,
                )
            )
            if is_live:
                alerts.append(
                    _alert(
                        code="broker_snapshot_missing",
                        message="live broker snapshot is unavailable",
                        severity="critical",
                        runtime_id=runtime_id,
                        runtime_profile=runtime_profile,
                        datastore_scope=datastore_scope,
                        is_live=is_live,
                        diagnostic_only=diagnostic_only,
                        generated_at=generated_at,
                        suggested_action="suspend_new_trading",
                    )
                )

    def _observe_numeric_delta(
        self,
        *,
        name: str,
        warning: float,
        critical: float,
        portfolio_value: float | None,
        broker_value: float | None,
        observations: list[AuditObservation],
        alerts: list[AuditAlert],
        runtime_id: str,
        runtime_profile: str,
        datastore_scope: str,
        is_live: bool,
        diagnostic_only: bool,
        generated_at: str,
    ) -> None:
        if portfolio_value is None or broker_value is None:
            return
        delta = abs(portfolio_value - broker_value)
        severity = _severity_for_delta(delta, warning=warning, critical=critical)
        if severity is None:
            return
        code = f"{name}_delta"
        observations.append(
            _observation(
                code=code,
                message=f"{name} differs between portfolio and broker snapshots",
                severity=severity,
                runtime_id=runtime_id,
                runtime_profile=runtime_profile,
                datastore_scope=datastore_scope,
                is_live=is_live,
                diagnostic_only=diagnostic_only,
                generated_at=generated_at,
                values={
                    "portfolio_value": portfolio_value,
                    "broker_value": broker_value,
                    "delta": delta,
                },
            )
        )
        if severity == "critical" and is_live:
            alerts.append(
                _alert(
                    code=code,
                    message=f"critical {name} audit delta",
                    severity=severity,
                    runtime_id=runtime_id,
                    runtime_profile=runtime_profile,
                    datastore_scope=datastore_scope,
                    is_live=is_live,
                    diagnostic_only=diagnostic_only,
                    generated_at=generated_at,
                    suggested_action="suspend_new_trading",
                )
            )

    def _observe_position_deltas(
        self,
        *,
        portfolio_snapshot: Any,
        broker_snapshot: Mapping[str, Any],
        observations: list[AuditObservation],
        alerts: list[AuditAlert],
        runtime_id: str,
        runtime_profile: str,
        datastore_scope: str,
        is_live: bool,
        diagnostic_only: bool,
        generated_at: str,
    ) -> None:
        portfolio_qty = _portfolio_positions_qty_by_symbol(portfolio_snapshot)
        broker_qty = _positions_mapping(broker_snapshot.get("positions_qty_by_symbol"))
        for symbol in sorted(set(portfolio_qty) | set(broker_qty)):
            delta = abs(portfolio_qty.get(symbol, 0.0) - broker_qty.get(symbol, 0.0))
            severity = _severity_for_delta(
                delta,
                warning=self.thresholds.position_qty_delta_warning,
                critical=self.thresholds.position_qty_delta_critical,
            )
            if severity is None:
                continue
            observations.append(
                _observation(
                    code="positions_qty_by_symbol_delta",
                    message="position quantity differs between portfolio and broker snapshots",
                    severity=severity,
                    runtime_id=runtime_id,
                    runtime_profile=runtime_profile,
                    datastore_scope=datastore_scope,
                    is_live=is_live,
                    diagnostic_only=diagnostic_only,
                    generated_at=generated_at,
                    values={
                        "symbol": symbol,
                        "portfolio_quantity": portfolio_qty.get(symbol, 0.0),
                        "broker_quantity": broker_qty.get(symbol, 0.0),
                        "delta": delta,
                    },
                )
            )
            if severity == "critical" and is_live:
                alerts.append(
                    _alert(
                        code="positions_qty_by_symbol_delta",
                        message="critical position quantity audit delta",
                        severity=severity,
                        runtime_id=runtime_id,
                        runtime_profile=runtime_profile,
                        datastore_scope=datastore_scope,
                        is_live=is_live,
                        diagnostic_only=diagnostic_only,
                        generated_at=generated_at,
                        suggested_action="suspend_new_trading",
                    )
                )


def _observation(
    *,
    code: str,
    message: str,
    severity: AuditSeverity,
    runtime_id: str,
    runtime_profile: str,
    datastore_scope: str,
    is_live: bool,
    diagnostic_only: bool,
    generated_at: str,
    values: dict[str, Any] | None = None,
) -> AuditObservation:
    return AuditObservation(
        code=code,
        message=message,
        severity=severity,
        runtime_id=runtime_id,
        runtime_profile=runtime_profile,
        datastore_scope=datastore_scope,
        is_live=is_live,
        generated_at=generated_at,
        diagnostic_only=diagnostic_only,
        values=values or {},
    )


def _alert(
    *,
    code: str,
    message: str,
    severity: AuditSeverity,
    runtime_id: str,
    runtime_profile: str,
    datastore_scope: str,
    is_live: bool,
    diagnostic_only: bool,
    generated_at: str,
    suggested_action: str | None,
) -> AuditAlert:
    return AuditAlert(
        code=code,
        message=message,
        severity=severity,
        runtime_id=runtime_id,
        runtime_profile=runtime_profile,
        datastore_scope=datastore_scope,
        is_live=is_live,
        generated_at=generated_at,
        diagnostic_only=diagnostic_only,
        suggested_action=suggested_action,
    )


def _severity_for_delta(
    delta: float,
    *,
    warning: float,
    critical: float,
) -> AuditSeverity | None:
    if delta >= critical:
        return "critical"
    if delta > warning:
        return "warning"
    return None


def _portfolio_number(portfolio: Any, name: str) -> float | None:
    metadata = getattr(portfolio, "metadata", None)
    if isinstance(metadata, Mapping):
        value = metadata.get(name)
        if isinstance(value, (int, float)):
            return float(value)
    value = getattr(portfolio, name, None)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _mapping_number(source: Mapping[str, Any], name: str) -> float | None:
    value = source.get(name)
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _portfolio_positions_qty_by_symbol(portfolio: Any) -> dict[str, float]:
    positions = getattr(portfolio, "positions", None)
    if not isinstance(positions, Mapping):
        return {}
    out: dict[str, float] = {}
    for position in positions.values():
        symbol = getattr(position, "instrument_id", None)
        quantity = getattr(position, "quantity", None)
        if not isinstance(symbol, str) or not isinstance(quantity, (int, float)):
            continue
        out[symbol] = out.get(symbol, 0.0) + float(quantity)
    return out


def _positions_mapping(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, float] = {}
    for symbol, quantity in value.items():
        if isinstance(symbol, str) and isinstance(quantity, (int, float)):
            out[symbol] = float(quantity)
    return out


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
