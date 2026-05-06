from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.orchestration.daemon_artifacts import write_daemon_artifacts
from app.orchestration.daemon_runner import DaemonSession, run_loop
from app.orchestration.run_cleanup import clean_runtime_paths
from app.orchestration.session_builder import RuntimeProfile, build_universe_session
from config.defaults import default_plan
from config.env import load_dotenv
from config.loader import load_plan
from config.models import RunPlan
from optimize.promoter.manifest_artifact import (
    manifest_safe_path,
    redacted_effective_plan_summary,
    redaction_status,
)
from optimize.promoter.promotion_gate import PromotionThresholds


def _plan_meta_for(path: Path | None, *, plan_obj: RunPlan) -> dict[str, Any]:
    plan_json = json.dumps(asdict(plan_obj), ensure_ascii=False, sort_keys=True, default=str)
    effective_config = json.loads(plan_json)
    effective_config_summary = redacted_effective_plan_summary(effective_config)
    if path is None:
        return {
            "path": None,
            "sha256": hashlib.sha256(plan_json.encode("utf-8")).hexdigest(),
            "effective_config_summary": effective_config_summary,
            "redaction_status": redaction_status(),
        }

    raw = path.read_bytes()
    return {
        "path": manifest_safe_path(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "effective_config_summary": effective_config_summary,
        "redaction_status": redaction_status(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_daemon",
        description="Run a long-running local/dryrun/live session.",
    )
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--runtime-id", type=str, default="rt_daemon")
    parser.add_argument("--profile", type=str, default="")
    parser.add_argument("--max-ticks", type=int, default=0)  # 0=forever
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--artifact-every", type=int, default=5)  # ticks; 0=disable
    parser.add_argument("--audit-enabled", type=int, default=0)
    parser.add_argument("--audit-interval-seconds", type=float, default=300.0)
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--stop-on-exception", type=int, default=1)
    args = parser.parse_args(argv)

    load_dotenv()

    plan_path = Path(args.config) if args.config else None
    if plan_path:
        plan = load_plan(plan_path, runtime_id=args.runtime_id)
    else:
        plan = default_plan(runtime_id=args.runtime_id)
    profile = str(args.profile or plan.runtime.mode).strip().lower()
    if profile not in {"local", "dryrun", "live"}:
        raise SystemExit("profile must be local|dryrun|live")
    if profile != plan.runtime.mode:
        raise ValueError(
            f"profile conflict: arg={profile!r} plan.runtime.mode={plan.runtime.mode!r}"
        )
    profile_typed: RuntimeProfile = profile

    if args.clean:
        clean_runtime_paths(
            runtime_id=args.runtime_id,
            store_root=plan.datastore.store_root,
            artifacts_root=plan.datastore.artifacts_root,
        )

    # Daemon keeps stable candidate_id per boot for audit
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    candidate_id = f"cand_{args.runtime_id}_daemon_{ts}"

    thresholds = PromotionThresholds(
        min_events=plan.promotion.min_events,
        min_success_rate_improvement=plan.promotion.min_success_rate_improvement,
        max_consecutive_failures=plan.promotion.max_consecutive_failures,
    )

    uni = build_universe_session(
        plan=plan,
        profile=profile_typed,
        runtime_id=args.runtime_id,
    )
    plan_meta = _plan_meta_for(plan_path, plan_obj=uni.plan)
    write_daemon_artifacts(
        runtime_id=args.runtime_id,
        scope=profile,
        store_root=plan.datastore.store_root,
        artifacts_root=plan.datastore.artifacts_root,
        candidate_id=candidate_id,
        thresholds=thresholds,
        plan_meta=plan_meta,
        write_manifest=True,
        write_summary=True,
        status="booting",
        include_strategy_switch=False,
    )

    session = DaemonSession(
        runtime_id=args.runtime_id,
        scope=profile,
        universe_runtime=uni,
        store_root=plan.datastore.store_root,
        artifacts_root=plan.datastore.artifacts_root,
        candidate_id=candidate_id,
        thresholds=thresholds,
        plan_meta=plan_meta,
        audit_enabled=int(args.audit_enabled) == 1,
        audit_interval_seconds=float(args.audit_interval_seconds),
    )

    _ = run_loop(
        session=session,
        max_ticks=int(args.max_ticks),
        interval_s=float(args.interval),
        stop_on_exception=int(args.stop_on_exception) == 1,
        artifact_every=int(args.artifact_every),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
