from __future__ import annotations

from domain.enums import Decision
from strategies.registry import StrategyRegistry


def test_strategy_force_decision_param_overrides_output() -> None:
    s = StrategyRegistry.create(name="simple_strategy", params={"force_decision": "HOLD"})
    d = s.generate("au", 100.0)
    assert d.decision == Decision.HOLD
