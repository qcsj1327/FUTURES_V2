from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.orchestration.daemon_artifacts import write_daemon_artifacts
from app.orchestration.daemon_runner import run_loop
from app.orchestration.session_builder import Env, build_universe_session
from config.defaults import default_plan
from config.loader import load_plan


def _rm_tree(p: Path) -> None:
    if p.exists():
        shutil.rmtree(p)


def _get_datastore(sess: Any) -> Any:
    ds = getattr(sess, "datastore", None)
    if ds is not None:
        return ds
    ex = getattr(sess, "executor", None)
    ds = getattr(ex, "datastore", None) if ex is not None else None
    if ds is not None:
        return ds
    rt = getattr(sess, "runtime", None)
    ds = getattr(rt, "datastore", None) if rt is not None else None
    if ds is not None:
        return ds
    raise RuntimeError("cannot locate datastore on session")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_daemon",
        description="Run a long-running live/sandbox session (writes store + minimal artifacts).",
    )
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--runtime-id", type=str, default="rt_daemon")
    parser.add_argument("--env", type=str, default="live")  # live|sandbox
    parser.add_argument("--max-ticks", type=int, default=0)  # 0=forever
    parser.add_argument("--interval", type=float, default=1.0)
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
        _rm_tree(plan.datastore.store_root / env / args.runtime_id)
        # keep artifacts, but if you want fully clean:
        _rm_tree(plan.datastore.artifacts_root)

    # plan_meta (only if config file provided)
    plan_meta: dict[str, Any] | None = None
    if plan_path is not None:
        raw = plan_path.read_bytes()
        plan_meta = {
            "path": str(plan_path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "config": json.loads(raw.decode("utf-8")),
        }

    session = build_universe_session(
        plan=plan,
        env=env_typed,
        runtime_id=args.runtime_id,
    )

    ds = _get_datastore(session)

    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    candidate_id = f"cand_{args.runtime_id}_daemon_{ts}"

    candidate_config = {
        "universe": {"symbols": list(plan.universe.symbols)},
        "strategies": [asdict(s) for s in plan.strategies],
    }
    thresholds = {
        "min_events": plan.promotion.min_events,
        "min_success_rate_improvement": plan.promotion.min_success_rate_improvement,
        "max_consecutive_failures": plan.promotion.max_consecutive_failures,
    }

    # Write an initial manifest immediately so inspect_run/watch_run works during daemon run.
    write_daemon_artifacts(
        runtime_id=args.runtime_id,
        env=env,
        datastore=ds,
        candidate_id=candidate_id,
        candidate_config=candidate_config,
        thresholds=thresholds,
        plan=(cast(dict[str, Any], plan_meta["config"]) if plan_meta else None),
        plan_path=(cast(str, plan_meta["path"]) if plan_meta else None),
        plan_sha256=(cast(str, plan_meta["sha256"]) if plan_meta else None),
        artifacts_root=plan.datastore.artifacts_root,
    )

    _ = run_loop(
        session=session,
        max_ticks=int(args.max_ticks),
        interval_s=float(args.interval),
        stop_on_exception=int(args.stop_on_exception) == 1,
    )

    # Refresh summary/manifest at the end (best-effort).
    write_daemon_artifacts(
        runtime_id=args.runtime_id,
        env=env,
        datastore=ds,
        candidate_id=candidate_id,
        candidate_config=candidate_config,
        thresholds=thresholds,
        plan=(cast(dict[str, Any], plan_meta["config"]) if plan_meta else None),
        plan_path=(cast(str, plan_meta["path"]) if plan_meta else None),
        plan_sha256=(cast(str, plan_meta["sha256"]) if plan_meta else None),
        artifacts_root=plan.datastore.artifacts_root,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
