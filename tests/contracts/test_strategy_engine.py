from __future__ import annotations

from domain.enums import Decision
from strategies.base.simple_strategy import StrategyEngine


def test_strategy_generates_signal() -> None:
    engine = StrategyEngine()

    signal = engine.generate("au", 120)

    assert signal.decision == Decision.OPEN_LONG


def test_strategy_no_signal() -> None:
    engine = StrategyEngine()

    signal = engine.generate("au", 80)

    assert signal.decision == Decision.HOLD
