from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from domain.enums import Decision
from domain.signal import SignalDecision
from strategies.strategy_set import TaggedDecision


@dataclass(frozen=True)
class RouterConfig:
    mode: str = "priority"         # priority | weighted_vote | netting
    tie_breaker: str = "priority"  # priority | lex


def _get_symbol(d: SignalDecision) -> str:
    for k in ("symbol", "instrument_id", "trade_instrument_id"):
        v = getattr(d, k, None)
        if isinstance(v, str) and v:
            return v
    return "UNKNOWN"


def _priority_key(td: TaggedDecision, priorities: dict[str, int]) -> tuple[int, str]:
    return (priorities.get(td.strategy_name, 1000), td.strategy_name)


def _decision_key(dec: Decision) -> str:
    return dec.name


def _vote_key(td: TaggedDecision, priorities: dict[str, int]) -> tuple[int, str]:
    # used as deterministic tiebreak for same score
    return _priority_key(td, priorities)


def route(
    tagged: list[TaggedDecision],
    *,
    config: RouterConfig,
    priorities: dict[str, int],
    weights: dict[str, float],
) -> list[TaggedDecision]:
    grouped: dict[str, list[TaggedDecision]] = defaultdict(list)
    for td in tagged:
        grouped[_get_symbol(td.decision)].append(td)

    out: list[TaggedDecision] = []
    for sym in sorted(grouped.keys()):
        group = grouped[sym]
        out.append(_route_one_symbol(group, config=config, priorities=priorities, weights=weights))
    return out


def _route_one_symbol(
    group: list[TaggedDecision],
    *,
    config: RouterConfig,
    priorities: dict[str, int],
    weights: dict[str, float],
) -> TaggedDecision:
    mode = config.mode

    if mode == "priority":
        return sorted(group, key=lambda td: _priority_key(td, priorities))[0]

    if mode == "weighted_vote":
        # score per decision name
        scores: dict[str, float] = {}
        buckets: dict[str, list[TaggedDecision]] = defaultdict(list)
        for td in group:
            dec = getattr(td.decision, "decision", None)
            if not isinstance(dec, Decision):
                continue
            name = _decision_key(dec)
            w = float(weights.get(td.strategy_name, 1.0))
            scores[name] = scores.get(name, 0.0) + w
            buckets[name].append(td)

        if not scores:
            return sorted(group, key=lambda td: _priority_key(td, priorities))[0]

        best_score = max(scores.values())
        best_names = sorted([k for k, v in scores.items() if v == best_score])

        chosen_name = best_names[0]
        if config.tie_breaker == "priority":
            return sorted(buckets[chosen_name], key=lambda td: _vote_key(td, priorities))[0]
        return sorted(buckets[chosen_name], key=lambda td: td.strategy_name)[0]

    if mode == "netting":
        # CLOSE dominates if any strategy says CLOSE (highest safety)
        close_candidates: list[TaggedDecision] = []
        long_score = 0.0
        short_score = 0.0

        for td in group:
            dec = getattr(td.decision, "decision", None)
            if not isinstance(dec, Decision):
                continue
            w = float(weights.get(td.strategy_name, 1.0))

            if dec == Decision.CLOSE:
                close_candidates.append(td)
            elif dec == Decision.OPEN_LONG:
                long_score += w
            elif dec == Decision.OPEN_SHORT:
                short_score += w
            else:
                # HOLD / other => ignore
                pass

        if close_candidates:
            return sorted(close_candidates, key=lambda td: _priority_key(td, priorities))[0]

        if long_score > short_score:
            # choose one of the OPEN_LONG recommendations (tie-break by priority)
            longs: list[TaggedDecision] = []
            for td in group:
                if getattr(td.decision, "decision", None) == Decision.OPEN_LONG:
                    longs.append(td)
            if longs:
                return sorted(longs, key=lambda td: _priority_key(td, priorities))[0]

        if short_score > long_score:
            shorts: list[TaggedDecision] = []
            for td in group:
                if getattr(td.decision, "decision", None) == Decision.OPEN_SHORT:
                    shorts.append(td)
            if shorts:
                return sorted(shorts, key=lambda td: _priority_key(td, priorities))[0]

        # net to HOLD (or fall back to highest priority HOLD if any, else priority)
        holds = [td for td in group if getattr(td.decision, "decision", None) == Decision.HOLD]
        if holds:
            return sorted(holds, key=lambda td: _priority_key(td, priorities))[0]
        return sorted(group, key=lambda td: _priority_key(td, priorities))[0]

    raise ValueError(f"unknown router mode: {mode}")
