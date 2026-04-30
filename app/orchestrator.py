from __future__ import annotations

from app.runtime import Runtime
from core.signal_router.signal_router import SignalRouter
from core.strategy_runner.strategy_runner import StrategyRunner
from strategies.registry import StrategyRegistry


class Orchestrator:
    def __init__(self, runtime: Runtime, registry: StrategyRegistry) -> None:
        self.runtime = runtime
        self.registry = registry

        self.runner = StrategyRunner(registry)
        self.router = SignalRouter()

    def run_once(self) -> None:
        price = self.runtime.market_data.get_last_price(self.runtime.config.symbol)

        signals = self.runner.run(self.runtime.config.symbol, price)
        decision = self.router.select(signals)

        self.runtime.run(decision)
