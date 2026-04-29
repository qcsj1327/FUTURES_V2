from __future__ import annotations

from core.strategy_engine.strategy_engine import StrategyEngine
from domain.enums import Decision


def test_strategy_generates_signal() -> None:
    engine = StrategyEngine()

    signal = engine.generate("au", 120)

    assert signal.decision == Decision.OPEN_LONG


def test_strategy_no_signal() -> None:
    engine = StrategyEngine()

    signal = engine.generate("au", 80)

    assert signal.decision == Decision.HOLD
