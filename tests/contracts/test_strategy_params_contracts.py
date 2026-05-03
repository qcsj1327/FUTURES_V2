from __future__ import annotations

from adapters.marketdata.base import MarketQuote
from domain.enums import Decision
from strategies.registry import StrategyRegistry


def test_strategy_force_decision_param_overrides_output() -> None:
    s = StrategyRegistry.create(name="simple_strategy", params={"force_decision": "HOLD"})
    d = s.generate("au", MarketQuote(symbol="au", price=100.0, volume=1000.0, ts=1))
    assert d.decision == Decision.HOLD
