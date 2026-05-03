from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StoreStats:
    fill_events_lines: int
    order_events_lines: int
    roll_events_lines: int
    rank_events_lines: int
    order_lifecycle_events_lines: int
    portfolio_snapshots_lines: int
    snapshot_pkls: int


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected json object: {path}")
    return data


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def _tail_jsonl(path: Path, n: int) -> list[dict[str, Any]]:
    if not path.exists() or n <= 0:
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-n:]
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _find_latest_manifest(*, runtime_id: str, manifests_dir: Path) -> Path | None:
    if not manifests_dir.exists():
        return None

    candidates: list[tuple[str, Path]] = []
    for p in manifests_dir.glob("manifest_*.json"):
        try:
            payload = _read_json(p)
        except Exception:
            continue
        if payload.get("kind") != "promotion_manifest":
            continue
        if str(payload.get("runtime_id", "")) != runtime_id:
            continue
        created = str(payload.get("created_at", ""))
        candidates.append((created, p))

    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[0], t[1].name))
    return candidates[-1][1]


def _store_stats(store_dir: Path) -> StoreStats:
    snap_dir = store_dir / "snapshots"
    snap_pkls = len(list(snap_dir.glob("*.pkl"))) if snap_dir.exists() else 0
    return StoreStats(
        fill_events_lines=_count_lines(store_dir / "fill_events.jsonl"),
        order_events_lines=_count_lines(store_dir / "order_events.jsonl"),
        roll_events_lines=_count_lines(store_dir / "roll_events.jsonl"),
        rank_events_lines=_count_lines(store_dir / "rank_events.jsonl"),
        order_lifecycle_events_lines=_count_lines(store_dir / "order_lifecycle_events.jsonl"),
        portfolio_snapshots_lines=_count_lines(store_dir / "portfolio_snapshots.jsonl"),
        snapshot_pkls=snap_pkls,
    )


def inspect_run(
    *,
    runtime_id: str,
    store_root: Path = Path("data/store"),
    artifacts_root: Path = Path("data/artifacts"),
    tail: int = 5,
) -> dict[str, Any]:
    manifests_dir = artifacts_root / "manifests"
    manifest_path = _find_latest_manifest(runtime_id=runtime_id, manifests_dir=manifests_dir)
    if manifest_path is None:
        raise FileNotFoundError(f"no manifest found for runtime_id={runtime_id} in {manifests_dir}")

    manifest = _read_json(manifest_path)

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}

    plan_meta = manifest.get("plan")
    if not isinstance(plan_meta, dict):
        plan_meta = {}

    plan_cfg_any = plan_meta.get("config")
    plan_cfg: dict[str, Any] = plan_cfg_any if isinstance(plan_cfg_any, dict) else {}

    def _maybe_read(path_str: Any) -> dict[str, Any] | None:
        if not isinstance(path_str, str) or not path_str:
            return None
        p = Path(path_str)
        if not p.exists():
            return None
        try:
            return _read_json(p)
        except Exception:
            return None

    current_summary = _maybe_read(artifacts.get("current_summary"))
    candidate_summary = _maybe_read(artifacts.get("candidate_summary"))
    decision = _maybe_read(artifacts.get("decision"))
    approved = _maybe_read(artifacts.get("approved"))

    live_dir = store_root / "live" / runtime_id
    sandbox_dir = store_root / "sandbox" / runtime_id

    out: dict[str, Any] = {
        "runtime_id": runtime_id,
        "manifest": {
            "path": str(manifest_path),
            "created_at": manifest.get("created_at"),
            "candidate_id": manifest.get("candidate_id"),
        },
        "plan": {
            "path": plan_meta.get("path"),
            "sha256": plan_meta.get("sha256"),
            "router": plan_cfg.get("router"),
            "universe": plan_cfg.get("universe"),
            "strategies": plan_cfg.get("strategies"),
        },
        "summaries": {"current": current_summary, "candidate": candidate_summary},
        "decision": decision,
        "approved": approved,
        "stores": {
            "live": {
                "dir": str(live_dir),
                "stats": _store_stats(live_dir).__dict__,
                "tail": {
                    "fill_events": _tail_jsonl(live_dir / "fill_events.jsonl", tail),
                    "order_events": _tail_jsonl(live_dir / "order_events.jsonl", tail),
                    "roll_events": _tail_jsonl(live_dir / "roll_events.jsonl", tail),
                    "rank_events": _tail_jsonl(live_dir / "rank_events.jsonl", tail),
                    "order_lifecycle_events": _tail_jsonl(
                        live_dir / "order_lifecycle_events.jsonl",
                        tail,
                    ),
                },
            },
            "sandbox": {
                "dir": str(sandbox_dir),
                "stats": _store_stats(sandbox_dir).__dict__,
                "tail": {
                    "fill_events": _tail_jsonl(sandbox_dir / "fill_events.jsonl", tail),
                    "order_events": _tail_jsonl(sandbox_dir / "order_events.jsonl", tail),
                    "roll_events": _tail_jsonl(sandbox_dir / "roll_events.jsonl", tail),
                    "rank_events": _tail_jsonl(sandbox_dir / "rank_events.jsonl", tail),
                    "order_lifecycle_events": _tail_jsonl(
                        sandbox_dir / "order_lifecycle_events.jsonl",
                        tail,
                    ),
                },
            },
        },
    }
    return out


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
