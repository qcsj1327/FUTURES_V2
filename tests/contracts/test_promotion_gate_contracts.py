from __future__ import annotations

import pytest

from optimize.promoter.promotion_gate import PromotionGate, PromotionThresholds


def test_promotion_gate_approves_when_thresholds_met() -> None:
    gate = PromotionGate(
        thresholds=PromotionThresholds(
            min_events=2,
            min_success_rate_improvement=0.10,
            max_consecutive_failures=2,
        )
    )

    current = {"total_events": 2, "success_rate": 0.50, "max_consecutive_failures": 2}
    candidate = {"total_events": 2, "success_rate": 0.70, "max_consecutive_failures": 1}

    decision = gate.evaluate(current=current, candidate=candidate)
    assert decision.approved is True
    assert decision.reasons == []
    assert decision.deltas["success_rate_delta"] == pytest.approx(0.20)


def test_promotion_gate_rejects_when_no_improvement() -> None:
    gate = PromotionGate(
        thresholds=PromotionThresholds(
            min_events=2,
            min_success_rate_improvement=0.10,
            max_consecutive_failures=2,
        )
    )

    current = {"total_events": 2, "success_rate": 0.60, "max_consecutive_failures": 0}
    candidate = {"total_events": 2, "success_rate": 0.65, "max_consecutive_failures": 0}

    decision = gate.evaluate(current=current, candidate=candidate)
    assert decision.approved is False
    assert "insufficient_success_rate_improvement" in decision.reasons


def test_promotion_gate_rejects_when_insufficient_events() -> None:
    gate = PromotionGate(
        thresholds=PromotionThresholds(
            min_events=5,
            min_success_rate_improvement=0.01,
            max_consecutive_failures=2,
        )
    )

    current = {"total_events": 100, "success_rate": 0.60, "max_consecutive_failures": 0}
    candidate = {"total_events": 2, "success_rate": 0.90, "max_consecutive_failures": 0}

    decision = gate.evaluate(current=current, candidate=candidate)
    assert decision.approved is False
    assert "insufficient_events" in decision.reasons


def test_promotion_gate_rejects_when_fail_streak_too_high() -> None:
    gate = PromotionGate(
        thresholds=PromotionThresholds(
            min_events=2,
            min_success_rate_improvement=0.01,
            max_consecutive_failures=1,
        )
    )

    current = {"total_events": 2, "success_rate": 0.50, "max_consecutive_failures": 0}
    candidate = {"total_events": 2, "success_rate": 0.80, "max_consecutive_failures": 3}

    decision = gate.evaluate(current=current, candidate=candidate)
    assert decision.approved is False
    assert "max_consecutive_failures_exceeded" in decision.reasons
