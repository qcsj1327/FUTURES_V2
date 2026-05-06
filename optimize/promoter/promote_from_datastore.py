from __future__ import annotations

from core.services.runtime.datastore import DataStore
from core.services.runtime.execution_summary import (
    replay_execution_events,
    summarize_execution_events,
)
from optimize.promoter.promotion_gate import PromotionDecision, PromotionGate, PromotionThresholds


def promote_from_datastore(
    *,
    current_store: DataStore,
    current_scope: str,
    candidate_store: DataStore,
    candidate_scope: str,
    thresholds: PromotionThresholds | None = None,
) -> PromotionDecision:
    """
    End-to-end: datastore -> replay -> summary -> promotion gate decision.

    This stays adapter-agnostic and does NOT modify runtime configs.
    """
    gate = PromotionGate(thresholds=thresholds)

    cur_events = replay_execution_events(current_store, scope=current_scope)
    cand_events = replay_execution_events(candidate_store, scope=candidate_scope)

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
