from __future__ import annotations

from collections import defaultdict

from domain.signal import SignalDecision


def _priority_key(d: SignalDecision, priorities: dict[str, int]) -> tuple[int, str]:
    name = getattr(d, "strategy_name", "")
    return (priorities.get(name, 1000), name)


def _get_symbol(d: SignalDecision) -> str:
    # best-effort: SignalDecision may expose symbol/instrument_id/trade_instrument_id
    for k in ("symbol", "instrument_id", "trade_instrument_id"):
        v = getattr(d, k, None)
        if isinstance(v, str) and v:
            return v
    return "UNKNOWN"


def route_signals(
    decisions: list[SignalDecision],
    *,
    priorities: dict[str, int],
) -> list[SignalDecision]:
    """
    Deterministic routing:
      - group by symbol
      - pick the decision from the highest-priority strategy (lowest priority number)
      - if no priority known, treat as 1000
    No silent fallback.
    """
    grouped: dict[str, list[SignalDecision]] = defaultdict(list)
    for d in decisions:
        grouped[_get_symbol(d)].append(d)

    routed: list[SignalDecision] = []
    for sym in sorted(grouped.keys()):
        ds = grouped[sym]
        ds_sorted = sorted(ds, key=lambda d: _priority_key(d, priorities))
        routed.append(ds_sorted[0])
    return routed
