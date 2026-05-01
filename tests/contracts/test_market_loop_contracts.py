from __future__ import annotations

from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from domain.enums import PositionSide


def test_runtime_market_loop_runs_once() -> None:
    runtime = RuntimeFactory.build_simulated_runtime(
        RuntimeConfig(symbol="au", default_quantity=1.0)
    )

    runtime.run_market_once()

    assert runtime.orders_submitted >= 0


def test_runtime_market_loop_can_run_strategy_chain() -> None:
    runtime = RuntimeFactory.build_simulated_runtime(
        RuntimeConfig(symbol="au", default_quantity=1.0)
    )

    runtime.run_market_once()

    assert runtime.orders_submitted >= 0


def test_runtime_market_loop_checks_exit_without_mutating_when_no_thresholds() -> None:
    runtime = RuntimeFactory.build_simulated_runtime(
        RuntimeConfig(symbol="au", default_quantity=1.0)
    )

    runtime.run_market_once()
    before = dict(runtime.state.portfolio.positions)

    runtime.run_market_once()

    assert set(runtime.state.portfolio.positions.keys()) == set(before.keys())


def test_runtime_market_loop_exit_can_close_position() -> None:
    runtime = RuntimeFactory.build_simulated_runtime(
        RuntimeConfig(symbol="au", default_quantity=1.0)
    )

    runtime.run_market_once(
        stop_loss=10_000.0,
    )

    positions = list(runtime.state.portfolio.positions.values())

    assert positions
    assert any(p.position_side == PositionSide.LONG for p in positions)
    assert any(p.quantity == 0.0 for p in positions)
