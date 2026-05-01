from __future__ import annotations

from domain.enums import Decision
from strategies.registry import StrategyRegistry


def test_strategy_by_symbol_force_decision_overrides_per_symbol() -> None:
    s = StrategyRegistry.create(
        name="simple_strategy",
        params={
            "by_symbol": {
                "au": {"force_decision": "HOLD"},
                "ag": {"force_decision": "OPEN_LONG"},
            }
        },
    )

    d_au = s.generate("au", 100.0)
    d_ag = s.generate("ag", 100.0)

    assert d_au.decision == Decision.HOLD
    assert d_ag.decision == Decision.OPEN_LONG
