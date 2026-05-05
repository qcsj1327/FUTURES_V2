from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.orchestration.daemon_artifacts import write_daemon_artifacts
from optimize.promoter.promotion_gate import PromotionThresholds


@dataclass(frozen=True)
class DaemonSession:
    """
    Optional typed wrapper for daemon run_loop.

    run_loop() remains permissive (accepts object), but scripts may import this
    type and/or wrap UniverseSession into DaemonSession for extra metadata.
    """

    universe_runtime: Any
    runtime_id: str
    env: str
    store_root: Path
    artifacts_root: Path
    thresholds: PromotionThresholds
    plan_meta: dict[str, Any] | None = None
    candidate_id: str | None = None


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
    """
    Backward compatible:
    - session can be UniverseSession (from session_builder) OR DaemonSession OR UniverseRuntime.
    - artifact_every defaults to 5 so older tests don't need to pass it.
    """
    s = session  # Any-like access via getattr

    universe_runtime = cast(Any, getattr(s, "universe_runtime", s))
    runtime_id = str(getattr(s, "runtime_id", ""))
    env = str(getattr(s, "env", "live"))

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

    candidate_id = getattr(s, "candidate_id", None)
    if not isinstance(candidate_id, str) or not candidate_id:
        candidate_id = f"cand_{runtime_id}_daemon_{_now_tag()}"

    # Start: ensure inspect_run has a manifest immediately
    write_daemon_artifacts(
        runtime_id=runtime_id,
        env=env,
        store_root=store_root,
        artifacts_root=artifacts_root,
        candidate_id=candidate_id,
        thresholds=thresholds,
        plan_meta=plan_meta,
        write_manifest=True,
        write_summary=True,
    )

    tick = 0
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
                        env=env,
                        store_root=store_root,
                        artifacts_root=artifacts_root,
                        candidate_id=candidate_id,
                        thresholds=thresholds,
                        plan_meta=plan_meta,
                        write_manifest=False,
                        write_summary=True,
                    )
                    raise
            tick += 1

            if artifact_every > 0 and tick % artifact_every == 0:
                write_daemon_artifacts(
                    runtime_id=runtime_id,
                    env=env,
                    store_root=store_root,
                    artifacts_root=artifacts_root,
                    candidate_id=candidate_id,
                    thresholds=thresholds,
                    plan_meta=plan_meta,
                    write_manifest=False,
                    write_summary=True,
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
        env=env,
        store_root=store_root,
        artifacts_root=artifacts_root,
        candidate_id=candidate_id,
        thresholds=thresholds,
        plan_meta=plan_meta,
        write_manifest=False,
        write_summary=True,
    )
    return tick
