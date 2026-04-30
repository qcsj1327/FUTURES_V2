from __future__ import annotations

from app.orchestrator import Orchestrator
from app.runtime import Runtime
from app.runtime_config import RuntimeConfig
from strategies.base.simple_strategy import StrategyEngine
from strategies.registry import StrategyRegistry


def test_orchestrator_runs() -> None:
    registry = StrategyRegistry()
    registry.register("simple", StrategyEngine())

    runtime = Runtime(RuntimeConfig(symbol="au", default_quantity=1.0))

    orch = Orchestrator(runtime, registry)
    orch.run_once()

    assert runtime.orders_submitted >= 0
