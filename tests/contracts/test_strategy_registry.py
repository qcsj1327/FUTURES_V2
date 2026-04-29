from __future__ import annotations

from strategies.base.simple_strategy import StrategyEngine
from strategies.registry import StrategyRegistry


def test_strategy_registry() -> None:
    registry = StrategyRegistry()

    strategy = StrategyEngine()
    registry.register("simple", strategy)

    assert registry.get("simple") is strategy
    assert "simple" in registry.all()
