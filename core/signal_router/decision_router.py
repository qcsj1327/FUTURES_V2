from __future__ import annotations

from collections import defaultdict

from domain.signal import SignalDecision
from strategies.strategy_set import TaggedDecision


def _key(td: TaggedDecision, priorities: dict[str, int]) -> tuple[int, str]:
    return (priorities.get(td.strategy_name, 1000), td.strategy_name)


def _get_symbol(d: SignalDecision) -> str:
    for k in ("symbol", "instrument_id", "trade_instrument_id"):
        v = getattr(d, k, None)
        if isinstance(v, str) and v:
            return v
    return "UNKNOWN"


def route_tagged_signals(
    tagged: list[TaggedDecision],
    *,
    priorities: dict[str, int],
) -> list[TaggedDecision]:
    grouped: dict[str, list[TaggedDecision]] = defaultdict(list)
    for td in tagged:
        grouped[_get_symbol(td.decision)].append(td)

    routed: list[TaggedDecision] = []
    for sym in sorted(grouped.keys()):
        group = grouped[sym]
        group_sorted = sorted(group, key=lambda td: _key(td, priorities))
        routed.append(group_sorted[0])
    return routed
