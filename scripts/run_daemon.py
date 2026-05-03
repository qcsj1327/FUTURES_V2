from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.orchestration.daemon_runner import DaemonSession, run_loop
from app.orchestration.run_cleanup import clean_runtime_paths
from app.orchestration.session_builder import Env, build_universe_session
from config.defaults import default_plan
from config.loader import load_plan
from config.models import RunPlan
from optimize.promoter.promotion_gate import PromotionThresholds


def _plan_meta_for(path: Path | None, *, plan_obj: RunPlan) -> dict[str, Any]:
    if path is None:
        plan_json = json.dumps(asdict(plan_obj), ensure_ascii=False, sort_keys=True, default=str)
        return {
            "path": None,
            "sha256": hashlib.sha256(plan_json.encode("utf-8")).hexdigest(),
            "config": json.loads(plan_json),
        }

    raw = path.read_bytes()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "config": json.loads(raw.decode("utf-8")),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_daemon",
        description="Run a long-running live/sandbox session (writes store + rolling summaries).",
    )
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--runtime-id", type=str, default="rt_daemon")
    parser.add_argument("--env", type=str, default="live")  # live|sandbox
    parser.add_argument("--max-ticks", type=int, default=0)  # 0=forever
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--artifact-every", type=int, default=5)  # ticks; 0=disable
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--stop-on-exception", type=int, default=1)
    args = parser.parse_args(argv)

    plan_path = Path(args.config) if args.config else None
    if plan_path:
        plan = load_plan(plan_path, runtime_id=args.runtime_id)
    else:
        plan = default_plan(runtime_id=args.runtime_id)

    env = str(args.env).strip().lower()
    if env not in {"live", "sandbox"}:
        raise SystemExit("env must be live|sandbox")
    env_typed = cast(Env, env)

    if args.clean:
        clean_runtime_paths(
            runtime_id=args.runtime_id,
            store_root=plan.datastore.store_root,
            artifacts_root=plan.datastore.artifacts_root,
        )

    # Session builder returns UniverseRuntime (single-env)
    uni = build_universe_session(plan=plan, env=env_typed, runtime_id=args.runtime_id)

    # Daemon keeps stable candidate_id per boot for audit
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    candidate_id = f"cand_{args.runtime_id}_daemon_{ts}"

    thresholds = PromotionThresholds(
        min_events=plan.promotion.min_events,
        min_success_rate_improvement=plan.promotion.min_success_rate_improvement,
        max_consecutive_failures=plan.promotion.max_consecutive_failures,
    )

    plan_meta = _plan_meta_for(plan_path, plan_obj=plan)

    session = DaemonSession(
        runtime_id=args.runtime_id,
        env=env,
        universe_runtime=uni,
        store_root=plan.datastore.store_root,
        artifacts_root=plan.datastore.artifacts_root,
        candidate_id=candidate_id,
        thresholds=thresholds,
        plan_meta=plan_meta,
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
