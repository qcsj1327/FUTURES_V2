from __future__ import annotations

from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from domain.enums import PositionSide
from domain.state import PositionKey


def test_sandbox_runtime_clones_live_state_without_sharing_references() -> None:
    live = RuntimeFactory.build_simulated_runtime(
        RuntimeConfig(symbol="au", default_quantity=1.0)
    )
    live.run_market_once()

    sandbox = RuntimeFactory.build_sandbox_runtime_from_live(live)

    assert sandbox is not live
    assert sandbox.state is not live.state
    assert sandbox.state.portfolio is not live.state.portfolio
    assert sandbox.state.portfolio.positions is not live.state.portfolio.positions

    key = PositionKey("au", "au_main", PositionSide.LONG)

    assert key in live.state.portfolio.positions
    assert key in sandbox.state.portfolio.positions
    assert sandbox.state.portfolio.positions[key] is not live.state.portfolio.positions[key]


def test_sandbox_position_mutation_does_not_mutate_live_position() -> None:
    live = RuntimeFactory.build_simulated_runtime(
        RuntimeConfig(symbol="au", default_quantity=1.0)
    )
    live.run_market_once()

    sandbox = RuntimeFactory.build_sandbox_runtime_from_live(live)
    key = PositionKey("au", "au_main", PositionSide.LONG)

    sandbox_position = sandbox.state.portfolio.positions[key]
    live_position = live.state.portfolio.positions[key]

    sandbox_position.quantity = 999.0

    assert live_position.quantity != sandbox_position.quantity
    assert live_position.quantity == 1.0


def test_sandbox_uses_simulated_adapters_by_default() -> None:
    live = RuntimeFactory.build_simulated_runtime(
        RuntimeConfig(symbol="au", default_quantity=1.0)
    )
    sandbox = RuntimeFactory.build_sandbox_runtime_from_live(live)

    assert sandbox.market_data is not live.market_data
    assert sandbox.execution.broker is not live.execution.broker
