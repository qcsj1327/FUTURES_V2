from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PromotionThresholds:
    min_events: int = 50
    min_success_rate_improvement: float = 0.01
    max_consecutive_failures: int = 3


@dataclass(frozen=True)
class PromotionDecision:
    approved: bool
    reasons: list[str]
    deltas: dict[str, Any]


class PromotionGate:
    """
    PromotionPlane gate: decide whether a candidate can be promoted.
    Inputs are plain mappings to avoid hard dependencies on research/core types.
    Expected keys (minimum):
      - total_events: int
      - success_rate: float
      - max_consecutive_failures: int
    """

    def __init__(self, *, thresholds: PromotionThresholds | None = None) -> None:
        self.thresholds = thresholds or PromotionThresholds()

    def evaluate(
        self,
        *,
        current: Mapping[str, Any],
        candidate: Mapping[str, Any],
    ) -> PromotionDecision:
        reasons: list[str] = []
        deltas: dict[str, Any] = {}

        cand_total = int(candidate.get("total_events", 0) or 0)
        if cand_total < self.thresholds.min_events:
            reasons.append("insufficient_events")

        cur_sr = float(current.get("success_rate", 0.0) or 0.0)
        cand_sr = float(candidate.get("success_rate", 0.0) or 0.0)
        deltas["success_rate_delta"] = cand_sr - cur_sr
        if cand_sr < cur_sr + self.thresholds.min_success_rate_improvement:
            reasons.append("insufficient_success_rate_improvement")

        cand_streak = int(candidate.get("max_consecutive_failures", 0) or 0)
        deltas["max_consecutive_failures"] = cand_streak
        if cand_streak > self.thresholds.max_consecutive_failures:
            reasons.append("max_consecutive_failures_exceeded")

        approved = len(reasons) == 0
        return PromotionDecision(approved=approved, reasons=reasons, deltas=deltas)
