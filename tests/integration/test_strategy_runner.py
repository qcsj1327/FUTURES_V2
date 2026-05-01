from __future__ import annotations

from core.strategy_runner.strategy_runner import StrategyRunner
from strategies.base.simple_strategy import StrategyEngine
from strategies.registry import StrategyRegistry


def test_strategy_runner_collects_signals() -> None:
    registry = StrategyRegistry()
    registry.register("s1", StrategyEngine())
    registry.register("s2", StrategyEngine())

    runner = StrategyRunner(registry)

    signals = runner.run("au", 120)

    assert len(signals) == 2
    assert all(s.symbol == "au" for s in signals)
