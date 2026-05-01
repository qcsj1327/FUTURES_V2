from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from core.services.runtime.datastore import DataStore


@dataclass(frozen=True)
class ReplaySummary:
    total_events: int
    success_count: int
    failure_count: int
    success_rate: float
    top_failure_reasons: list[tuple[str, int]]


def replay_execution_events(
    store: DataStore,
    *,
    env: str,
) -> list[dict[str, Any]]:
    """Read execution events and return them sorted by ts (stable for analysis)."""
    events = store.read_fill_events(env=env)
    # ensure deterministic ordering
    return sorted(events, key=lambda e: int(e.get("ts", 0)))


def summarize_execution_events(
    events: list[dict[str, Any]],
) -> ReplaySummary:
    total = len(events)
    success = 0
    failure = 0
    reasons: Counter[str] = Counter()

    for e in events:
        ok = bool(e.get("success", False))
        if ok:
            success += 1
        else:
            failure += 1
            reason = e.get("reason") or e.get("rejected_reason") or "unknown"
            reasons[str(reason)] += 1

    rate = (success / total) if total > 0 else 0.0
    return ReplaySummary(
        total_events=total,
        success_count=success,
        failure_count=failure,
        success_rate=rate,
        top_failure_reasons=reasons.most_common(5),
    )
