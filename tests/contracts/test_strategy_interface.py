from __future__ import annotations

from strategies.base.simple_strategy import StrategyEngine
from strategies.base.strategy import Strategy


def test_strategy_implements_interface() -> None:
    strategy = StrategyEngine()

    assert isinstance(strategy, Strategy)
