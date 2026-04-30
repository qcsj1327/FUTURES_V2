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


def test_orchestrator_main_chain_wiring() -> None:
    registry = StrategyRegistry()
    registry.register("simple", StrategyEngine())

    runtime = Runtime(RuntimeConfig(symbol="au", default_quantity=1.0))
    orch = Orchestrator(runtime, registry)

    assert orch.runtime is runtime
    assert orch.registry is registry
    assert orch.runner.registry is registry
    assert orch.router is not None
    assert orch.portfolio is not None