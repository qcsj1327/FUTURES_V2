from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.orchestration.run_plan_orchestrator import (
    compute_plan_meta_from_file,
    orchestrate,
    resolve_plan,
)
from config.defaults import default_plan
from config.env import load_dotenv
from config.loader import load_plan


def _plan_meta_for(plan_path: Path | None, *, plan_obj: Any) -> dict[str, Any] | None:
    if plan_path is None:
        # still provide meta for audit consistency when running default plan
        plan_json = json.dumps(asdict(plan_obj), ensure_ascii=False, sort_keys=True, default=str)
        return {
            "path": None,
            "sha256": hashlib.sha256(plan_json.encode("utf-8")).hexdigest(),
            "config": json.loads(plan_json),
        }
    return compute_plan_meta_from_file(plan_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_plan",
        description="Run a full plan (multi-symbol/multi-strategy) end-to-end.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="",
        help="Optional plan json (schema_version=1).",
    )
    parser.add_argument("--runtime-id", type=str, default="r_plan")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args(argv)

    load_dotenv()

    plan_path = Path(args.config) if args.config else None
    if plan_path is not None:
        plan = load_plan(plan_path, runtime_id=args.runtime_id)
    else:
        plan = default_plan(runtime_id=args.runtime_id)

    plan_meta = _plan_meta_for(plan_path, plan_obj=plan)
    resolved = resolve_plan(plan=plan, plan_meta=plan_meta)

    result = orchestrate(resolved=resolved, clean=args.clean)

    # Keep CLI output stable: print decision if present, else print result
    if result.decision_path:
        payload = json.loads(Path(result.decision_path).read_text(encoding="utf-8"))
        decision = payload.get("decision") if isinstance(payload, dict) else None
        print(json.dumps(decision, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2, default=str))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
