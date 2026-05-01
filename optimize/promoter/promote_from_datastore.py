from __future__ import annotations

from core.services.runtime.datastore import DataStore
from optimize.promoter.promotion_gate import PromotionDecision, PromotionGate, PromotionThresholds
from research.datastore_replay import replay_execution_events, summarize_execution_events


def promote_from_datastore(
    *,
    current_store: DataStore,
    current_env: str,
    candidate_store: DataStore,
    candidate_env: str,
    thresholds: PromotionThresholds | None = None,
) -> PromotionDecision:
    """
    End-to-end: datastore -> replay -> summary -> promotion gate decision.

    This stays adapter-agnostic and does NOT modify runtime configs.
    """
    gate = PromotionGate(thresholds=thresholds)

    cur_events = replay_execution_events(current_store, env=current_env)
    cand_events = replay_execution_events(candidate_store, env=candidate_env)

    cur_summary = summarize_execution_events(cur_events)
    cand_summary = summarize_execution_events(cand_events)

    # PromotionGate expects plain mappings (avoid tight coupling to dataclass)
    current = {
        "total_events": cur_summary.total_events,
        "success_rate": cur_summary.success_rate,
        "max_consecutive_failures": cur_summary.max_consecutive_failures,
    }
    candidate = {
        "total_events": cand_summary.total_events,
        "success_rate": cand_summary.success_rate,
        "max_consecutive_failures": cand_summary.max_consecutive_failures,
    }

    return gate.evaluate(current=current, candidate=candidate)
