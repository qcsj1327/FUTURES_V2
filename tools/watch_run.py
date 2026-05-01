from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Any

from tools.inspect_run import inspect_run


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _fmt_line(report: dict[str, Any]) -> str:
    rid = str(report.get("runtime_id", ""))

    man = _as_dict(report.get("manifest"))
    created = str(man.get("created_at", ""))

    decision_root = _as_dict(report.get("decision"))
    decision_obj = _as_dict(decision_root.get("decision"))
    approved = decision_obj.get("approved")
    reasons = decision_obj.get("reasons")

    stores = _as_dict(report.get("stores"))
    live = _as_dict(stores.get("live"))
    sandbox = _as_dict(stores.get("sandbox"))

    live_stats = _as_dict(live.get("stats"))
    sb_stats = _as_dict(sandbox.get("stats"))
    live_fill = live_stats.get("fill_events_lines")
    sb_fill = sb_stats.get("fill_events_lines")

    plan = _as_dict(report.get("plan"))
    router = _as_dict(plan.get("router"))
    router_mode = router.get("mode")

    return (
        f"{created} rid={rid} router={router_mode} "
        f"approved={approved} reasons={reasons} "
        f"live.fill={live_fill} sandbox.fill={sb_fill}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="watch_run",
        description="Watch a run by polling inspect_run (read-only).",
    )
    parser.add_argument("runtime_id", type=str)
    parser.add_argument("--store-root", type=str, default="data/store")
    parser.add_argument("--artifacts-root", type=str, default="data/artifacts")
    parser.add_argument(
        "--tail",
        type=int,
        default=2,
        help="Tail N events per store (kept in report, not printed).",
    )
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="0=forever, else number of iterations.",
    )
    args = parser.parse_args(argv)

    i = 0
    while True:
        rep = inspect_run(
            runtime_id=args.runtime_id,
            store_root=Path(args.store_root),
            artifacts_root=Path(args.artifacts_root),
            tail=args.tail,
        )
        print(_fmt_line(rep), flush=True)

        i += 1
        if args.count > 0 and i >= args.count:
            break
        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
