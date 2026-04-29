from __future__ import annotations

from app.runtime import Runtime
from core.strategy_engine.strategy_engine import StrategyEngine


class AutoRunner:
    def __init__(self, runtime: Runtime) -> None:
        self.runtime = runtime
        self.strategy = StrategyEngine()
        self.market = runtime.market_data

    def run_once(self) -> None:
        price = self.market.get_last_price(self.runtime.config.symbol)
        decision = self.strategy.generate(self.runtime.config.symbol, price)
        self.runtime.run(decision)
