from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _tail_jsonl(path: Path, *, n: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    tail = lines[-n:] if n > 0 else lines
    out: list[dict[str, Any]] = []
    for s in tail:
        try:
            v = json.loads(s)
        except Exception:
            continue
        if isinstance(v, dict):
            out.append(v)
    return out


def get_run_events(
    *,
    runtime_id: str,
    env: str = "live",
    tail: int = 50,
    store_root: Path = Path("data/store"),
) -> dict[str, Any]:
    base = store_root / env / runtime_id
    fill_path = base / "fill_events.jsonl"
    order_path = base / "order_events.jsonl"

    fill_events = _tail_jsonl(fill_path, n=tail)
    order_events = _tail_jsonl(order_path, n=tail)

    return {
        "runtime_id": runtime_id,
        "env": env,
        "tail": tail,
        "paths": {
            "fill_events": str(fill_path),
            "order_events": str(order_path),
        },
        "fill_events": fill_events,
        "order_events": order_events,
    }
