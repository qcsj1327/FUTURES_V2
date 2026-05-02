from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.orchestration.run_plan_orchestrator import resolve_plan
from config.loader import load_plan


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="print_plan",
        description="Print resolved run plan (no execution).",
    )
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--runtime-id", type=str, default="r_plan")
    args = parser.parse_args(argv)

    plan_path = Path(args.config) if args.config else None
    plan = load_plan(plan_path, runtime_id=args.runtime_id)

    plan_meta: dict[str, Any] | None
    if plan_path is not None:
        raw = plan_path.read_bytes()
        plan_meta = {
            "path": str(plan_path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "config": json.loads(raw.decode("utf-8")),
        }
    else:
        plan_json = json.dumps(asdict(plan), ensure_ascii=False, sort_keys=True, default=str)
        plan_meta = {
            "path": None,
            "sha256": hashlib.sha256(plan_json.encode("utf-8")).hexdigest(),
            "config": json.loads(plan_json),
        }

    resolved = resolve_plan(plan=plan, plan_meta=plan_meta)

    payload = {
        "runtime_id": resolved.runtime_id,
        "env": resolved.env,
        "router": asdict(plan.router),
        "universe": asdict(plan.universe),
        "strategies": [asdict(s) for s in plan.strategies],
        "runtime": asdict(plan.runtime),
        "promotion": asdict(plan.promotion),
        "adapters": asdict(plan.adapters),
        "datastore": {
            "store_root": str(plan.datastore.store_root),
            "artifacts_root": str(plan.datastore.artifacts_root),
            "approved_dir": str(plan.datastore.approved_dir),
            "decisions_dir": str(plan.datastore.decisions_dir),
            "summaries_dir": str(plan.datastore.summaries_dir),
            "manifests_dir": str(plan.datastore.manifests_dir),
        },
        "plan_meta": resolved.plan_meta,
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
