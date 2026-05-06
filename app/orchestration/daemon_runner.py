from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.orchestration.audit_runner import (
    broker_snapshot_provider_from_universe,
    portfolio_snapshot_from_universe,
    run_audit_sidecar,
)
from app.orchestration.daemon_artifacts import write_daemon_artifacts
from core.services.audit.contracts import AuditThresholds
from optimize.promoter.promotion_gate import PromotionThresholds


@dataclass(frozen=True)
class DaemonSession:
    universe_runtime: Any
    runtime_id: str
    scope: str
    store_root: Path
    artifacts_root: Path
    thresholds: PromotionThresholds
    plan_meta: dict[str, Any] | None = None
    candidate_id: str | None = None
    audit_enabled: bool = False
    audit_interval_seconds: float = 300.0
    audit_thresholds: AuditThresholds | None = None


def _now_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _coerce_path(v: object, default: Path) -> Path:
    if isinstance(v, Path):
        return v
    if v is None:
        return default
    return Path(str(v))


def run_loop(
    *,
    session: object,
    max_ticks: int,
    interval_s: float,
    stop_on_exception: bool,
    artifact_every: int = 5,
) -> int:
    s = cast(Any, session)

    universe_runtime = cast(Any, s.universe_runtime)
    runtime_id = str(s.runtime_id)
    scope = str(s.scope)

    store_root = _coerce_path(getattr(s, "store_root", None), Path("data/store"))
    artifacts_root = _coerce_path(getattr(s, "artifacts_root", None), Path("data/artifacts"))

    thresholds = getattr(
        s,
        "thresholds",
        PromotionThresholds(
            min_events=1,
            min_success_rate_improvement=-1.0,
            max_consecutive_failures=99,
        ),
    )
    plan_meta = getattr(s, "plan_meta", None)
    audit_enabled = bool(getattr(s, "audit_enabled", False))
    audit_interval_seconds = float(getattr(s, "audit_interval_seconds", 300.0) or 0.0)
    audit_thresholds = getattr(s, "audit_thresholds", None)

    candidate_id = getattr(s, "candidate_id", None)
    if not isinstance(candidate_id, str) or not candidate_id:
        candidate_id = f"cand_{runtime_id}_daemon_{_now_tag()}"

    # Start: ensure inspect_run has a manifest immediately
    write_daemon_artifacts(
        runtime_id=runtime_id,
        scope=scope,
        store_root=store_root,
        artifacts_root=artifacts_root,
        candidate_id=candidate_id,
        thresholds=thresholds,
        plan_meta=plan_meta,
        write_manifest=True,
        write_summary=True,
        status="running",
    )

    tick = 0
    last_audit_at: float | None = None
    try:
        while True:
            if max_ticks > 0 and tick >= max_ticks:
                break

            try:
                universe_runtime.run_tick()
            except Exception:
                if stop_on_exception:
                    write_daemon_artifacts(
                        runtime_id=runtime_id,
                        scope=scope,
                        store_root=store_root,
                        artifacts_root=artifacts_root,
                        candidate_id=candidate_id,
                        thresholds=thresholds,
                        plan_meta=plan_meta,
                        write_manifest=False,
                        write_summary=True,
                        status="error",
                    )
                    raise
            tick += 1

            if _audit_due(
                enabled=audit_enabled,
                now=time.monotonic(),
                last_audit_at=last_audit_at,
                interval_seconds=audit_interval_seconds,
            ):
                last_audit_at = time.monotonic()
                _run_audit_sidecar_best_effort(
                    universe_runtime=universe_runtime,
                    runtime_id=runtime_id,
                    scope=scope,
                    artifacts_root=artifacts_root,
                    thresholds=audit_thresholds,
                )

            if artifact_every > 0 and tick % artifact_every == 0:
                write_daemon_artifacts(
                    runtime_id=runtime_id,
                    scope=scope,
                    store_root=store_root,
                    artifacts_root=artifacts_root,
                    candidate_id=candidate_id,
                    thresholds=thresholds,
                    plan_meta=plan_meta,
                    write_manifest=False,
                    write_summary=True,
                    status="running",
                )

            if interval_s > 0:
                time.sleep(interval_s)
    finally:
        close = getattr(universe_runtime, "close", None)
        if callable(close):
            close()

    # End: final refresh
    write_daemon_artifacts(
        runtime_id=runtime_id,
        scope=scope,
        store_root=store_root,
        artifacts_root=artifacts_root,
        candidate_id=candidate_id,
        thresholds=thresholds,
        plan_meta=plan_meta,
        write_manifest=False,
        write_summary=True,
        status="final",
    )
    return tick


def _audit_due(
    *,
    enabled: bool,
    now: float,
    last_audit_at: float | None,
    interval_seconds: float,
) -> bool:
    if not enabled:
        return False
    if last_audit_at is None:
        return True
    return interval_seconds <= 0 or now - last_audit_at >= interval_seconds


def _run_audit_sidecar_best_effort(
    *,
    universe_runtime: Any,
    runtime_id: str,
    scope: str,
    artifacts_root: Path,
    thresholds: AuditThresholds | None,
) -> None:
    try:
        run_audit_sidecar(
            runtime_id=runtime_id,
            runtime_profile=scope,
            datastore_scope=scope,
            portfolio_snapshot=portfolio_snapshot_from_universe(universe_runtime),
            broker_snapshot_provider=broker_snapshot_provider_from_universe(universe_runtime),
            artifacts_root=artifacts_root,
            thresholds=thresholds,
            store_scope=scope,
            artifact_scope=scope,
        )
    except Exception:
        return
