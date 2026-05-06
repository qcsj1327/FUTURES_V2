from __future__ import annotations

from pathlib import Path
from typing import Any

from web.readmodel.event_rows import CANONICAL_SCOPES, read_valid_event_rows

EVENT_FILES = {
    "fill_events": "fill_events.jsonl",
    "order_events": "order_events.jsonl",
    "roll_events": "roll_events.jsonl",
    "rank_events": "rank_events.jsonl",
    "strategy_score_events": "strategy_score_events.jsonl",
    "order_lifecycle_events": "order_lifecycle_events.jsonl",
}


def _tail_jsonl(
    path: Path, *, n: int, scope: str
) -> tuple[list[dict[str, Any]], int, dict[str, int]]:
    result = read_valid_event_rows(path, expected_scope=scope, tail=n)
    return result.rows, result.invalid_count, result.invalid_reasons


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
    scope: str = "live",
    tail: int = 50,
    store_root: Path = Path("data/store"),
    # filters
    since_ts: int | None = None,
    event_type: str | None = None,  # order|fill|roll|rank|order_lifecycle|strategy_score
    strategy_id: str | None = None,
    success: str | None = None,
    # pagination (timeline)
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    if scope not in CANONICAL_SCOPES:
        raise ValueError(f"invalid scope: {scope}")
    base = store_root / scope / runtime_id
    paths = {name: base / filename for name, filename in EVENT_FILES.items()}
    invalid_count = 0
    invalid_reasons: dict[str, int] = {}

    def _read(name: str) -> list[dict[str, Any]]:
        nonlocal invalid_count
        rows, count, reasons = _tail_jsonl(paths[name], n=tail, scope=scope)
        invalid_count += count
        for reason, reason_count in reasons.items():
            invalid_reasons[reason] = invalid_reasons.get(reason, 0) + reason_count
        return rows

    fill_events = _read("fill_events")
    order_events = _read("order_events")
    roll_events = _read("roll_events")
    rank_events = _read("rank_events")
    strategy_score_events = _read("strategy_score_events")
    order_lifecycle_events = _read("order_lifecycle_events")

    timeline_all = sorted(
        [
            *order_events,
            *fill_events,
            *roll_events,
            *rank_events,
            *strategy_score_events,
            *order_lifecycle_events,
        ],
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

    if limit < 1:
        limit = 1
    if limit > 5000:
        limit = 5000
    if offset < 0:
        offset = 0

    page = filtered[offset : offset + limit]

    return {
        "runtime_id": runtime_id,
        "scope": scope,
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
            name: str(path) for name, path in paths.items()
        },
        "invalid_count": invalid_count,
        "invalid_reasons": dict(sorted(invalid_reasons.items())),
        "fill_events": fill_events,
        "order_events": order_events,
        "roll_events": roll_events,
        "rank_events": rank_events,
        "strategy_score_events": strategy_score_events,
        "order_lifecycle_events": order_lifecycle_events,
        "timeline_total": len(timeline_all),
        "timeline_filtered_total": len(filtered),
        "timeline": page,
    }
