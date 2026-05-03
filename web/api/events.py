from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _tail_jsonl(path: Path, *, n: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    tail_lines = lines[-n:] if n > 0 else lines
    out: list[dict[str, Any]] = []
    for s in tail_lines:
        try:
            v = json.loads(s)
        except Exception:
            continue
        if isinstance(v, dict):
            out.append(v)
    return out


def _ts(ev: dict[str, Any]) -> int:
    t = ev.get("ts")
    return int(t) if isinstance(t, int) else 0


def _parse_bool(s: str) -> bool | None:
    v = s.strip().lower()
    if v == "true":
        return True
    if v == "false":
        return False
    return None


def get_run_events(
    *,
    runtime_id: str,
    env: str = "live",
    tail: int = 50,
    store_root: Path = Path("data/store"),
    # filters
    since_ts: int | None = None,
    event_type: str | None = None,  # order|execution
    strategy_id: str | None = None,
    success: str | None = None,  # true|false (execution only)
    # pagination (timeline)
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    base = store_root / env / runtime_id
    fill_path = base / "fill_events.jsonl"
    order_path = base / "order_events.jsonl"
    roll_path = base / "roll_events.jsonl"

    fill_events = _tail_jsonl(fill_path, n=tail)
    order_events = _tail_jsonl(order_path, n=tail)
    roll_events = _tail_jsonl(roll_path, n=tail)

    timeline_all = sorted(
        [*order_events, *fill_events, *roll_events],
        key=lambda x: (_ts(x), str(x.get("event_type", ""))),
    )

    filtered = timeline_all

    if since_ts is not None:
        filtered = [ev for ev in filtered if _ts(ev) >= since_ts]

    et = (event_type or "").strip()
    if et:
        filtered = [ev for ev in filtered if str(ev.get("event_type", "")) == et]

    sid = (strategy_id or "").strip()
    if sid:
        filtered = [ev for ev in filtered if str(ev.get("strategy_id", "")) == sid]

    sflag = _parse_bool(success or "")
    if sflag is not None:
        filtered = [
            ev
            for ev in filtered
            if str(ev.get("event_type", "")) == "execution"
            and bool(ev.get("success", False)) is sflag
        ]

    if limit < 1:
        limit = 1
    if limit > 5000:
        limit = 5000
    if offset < 0:
        offset = 0

    page = filtered[offset : offset + limit]

    return {
        "runtime_id": runtime_id,
        "env": env,
        "tail": tail,
        "filters": {
            "since_ts": since_ts,
            "event_type": et or None,
            "strategy_id": sid or None,
            "success": (success or "").strip() or None,
            "limit": limit,
            "offset": offset,
        },
        "paths": {
            "fill_events": str(fill_path),
            "order_events": str(order_path),
            "roll_events": str(roll_path),
        },
        "fill_events": fill_events,
        "order_events": order_events,
        "roll_events": roll_events,
        "timeline_total": len(timeline_all),
        "timeline_filtered_total": len(filtered),
        "timeline": page,
    }
