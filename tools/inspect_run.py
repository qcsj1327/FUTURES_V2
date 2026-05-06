from __future__ import annotations

import argparse
import json
from pathlib import Path

from web.readmodel.dashboard import _execution_observability, inspect_run

__all__ = ["_execution_observability", "inspect_run", "main"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="inspect_run",
        description="Inspect a run by runtime_id (read-only).",
    )
    parser.add_argument("runtime_id", type=str)
    parser.add_argument("--store-root", type=str, default="data/store")
    parser.add_argument("--artifacts-root", type=str, default="data/artifacts")
    parser.add_argument("--tail", type=int, default=5)
    args = parser.parse_args(argv)

    report = inspect_run(
        runtime_id=args.runtime_id,
        store_root=Path(args.store_root),
        artifacts_root=Path(args.artifacts_root),
        tail=args.tail,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
