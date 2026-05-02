from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from config.defaults import default_plan
from config.loader import load_plan
from config.models import RunPlan


def _plan_meta_for(path: Path | None, *, plan_obj: RunPlan) -> dict[str, Any]:
    if path is not None:
        raw = path.read_bytes()
        return {
            "path": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "config": json.loads(raw.decode("utf-8")),
        }
    plan_json = json.dumps(asdict(plan_obj), ensure_ascii=False, sort_keys=True, default=str)
    return {
        "path": None,
        "sha256": hashlib.sha256(plan_json.encode("utf-8")).hexdigest(),
        "config": json.loads(plan_json),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_plan",
        description="Validate and print a RunPlan (strict loader + defaults).",
    )
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--runtime-id", type=str, default="r_plan")
    args = parser.parse_args(argv)

    plan_path = Path(args.config) if args.config else None
    plan = (
        load_plan(plan_path, runtime_id=args.runtime_id)
        if plan_path
        else default_plan(runtime_id=args.runtime_id)
    )
    meta = _plan_meta_for(plan_path, plan_obj=plan)

    payload = {
        "runtime_id": plan.runtime.runtime_id,
        "env": plan.env,
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
        "plan_meta": meta,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
