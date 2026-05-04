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
    failure_reason_counts: dict[str, int]

    filled_quantity_sum: float
    filled_quantity_mean: float
    avg_fill_price_mean: float
    commission_sum: float
    slippage_sum: float
    cost_total_sum: float
    notional_sum: float

    event_count_by_strategy_name: dict[str, int]
    max_consecutive_failures: int


def replay_execution_events(
    store: DataStore,
    *,
    env: str,
) -> list[dict[str, Any]]:
    """Read execution events and return them sorted by ts (stable for analysis)."""
    events = store.read_fill_events(env=env)
    return sorted(events, key=lambda e: int(e.get("ts", 0)))


def summarize_execution_events(
    events: list[dict[str, Any]],
) -> ReplaySummary:
    total = len(events)
    success = 0
    failure = 0

    reasons: Counter[str] = Counter()
    by_strategy: Counter[str] = Counter()

    filled_sum = 0.0
    filled_n = 0

    price_sum = 0.0
    price_n = 0
    commission_sum = 0.0
    slippage_sum = 0.0
    cost_total_sum = 0.0
    notional_sum = 0.0

    max_fail_streak = 0
    cur_fail_streak = 0

    for e in events:
        by_strategy[str(e.get("strategy_name", "unknown"))] += 1

        ok = bool(e.get("success", False))
        if ok:
            success += 1
            cur_fail_streak = 0
        else:
            failure += 1
            cur_fail_streak += 1
            if cur_fail_streak > max_fail_streak:
                max_fail_streak = cur_fail_streak

            reason = e.get("reason") or e.get("rejected_reason") or "unknown"
            reasons[str(reason)] += 1

        fq = e.get("filled_quantity")
        if isinstance(fq, (int, float)):
            filled_sum += float(fq)
            filled_n += 1

        ap = e.get("avg_fill_price")
        if isinstance(ap, (int, float)):
            price_sum += float(ap)
            price_n += 1
        commission_sum += _float_field(e, "commission")
        slippage_sum += _float_field(e, "slippage")
        cost_total_sum += _float_field(e, "cost_total")
        notional_sum += _float_field(e, "notional")

    rate = (success / total) if total > 0 else 0.0
    filled_mean = (filled_sum / filled_n) if filled_n > 0 else 0.0
    price_mean = (price_sum / price_n) if price_n > 0 else 0.0

    return ReplaySummary(
        total_events=total,
        success_count=success,
        failure_count=failure,
        success_rate=rate,
        top_failure_reasons=reasons.most_common(5),
        failure_reason_counts=dict(reasons),
        filled_quantity_sum=filled_sum,
        filled_quantity_mean=filled_mean,
        avg_fill_price_mean=price_mean,
        commission_sum=commission_sum,
        slippage_sum=slippage_sum,
        cost_total_sum=cost_total_sum,
        notional_sum=notional_sum,
        event_count_by_strategy_name=dict(by_strategy),
        max_consecutive_failures=max_fail_streak,
    )


def _float_field(event: dict[str, Any], key: str) -> float:
    value = event.get(key)
    return float(value) if isinstance(value, (int, float)) else 0.0
