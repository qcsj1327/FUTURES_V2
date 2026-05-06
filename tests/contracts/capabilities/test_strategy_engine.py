from __future__ import annotations

from core.services.marketdata.types import MarketQuote
from domain.enums import Decision
from strategies.base.simple_strategy import StrategyEngine


def test_strategy_generates_signal() -> None:
    engine = StrategyEngine()

    signal = engine.generate("au", MarketQuote(symbol="au", price=120.0, volume=1000.0, ts=1))

    assert signal.decision == Decision.OPEN_LONG


def test_strategy_no_signal() -> None:
    engine = StrategyEngine()

    signal = engine.generate("au", MarketQuote(symbol="au", price=80.0, volume=1000.0, ts=1))

    assert signal.decision == Decision.HOLD
