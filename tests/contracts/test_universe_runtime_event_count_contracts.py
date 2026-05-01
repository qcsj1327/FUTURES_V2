from __future__ import annotations

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from app.universe_runtime import UniverseRuntime
from core.signal_router.router import RouterConfig
from strategies.registry import StrategyRegistry
from strategies.strategy_set import StrategyEntry, StrategySet


def test_universe_runtime_fill_events_count_matches_symbols_times_ticks() -> None:
    cfg = RuntimeConfig()
    store = MemoryDataStore(env="sandbox", runtime_id=cfg.runtime_id)

    md = SimulatedMarketData()
    broker = SimulatedBroker(md)

    executor = RuntimeFactory.build_runtime(
        config=cfg,
        market_data=md,
        broker=broker,
        environment="sandbox",
        datastore=store,
    )

    symbols = ["au", "ag", "rb"]
    ticks = 4

    # Force HOLD to avoid exits and keep deterministic counts.
    strat = StrategyRegistry.create(name="simple_strategy", params={"force_decision": "HOLD"})
    entry = StrategyEntry(
        name="simple_strategy",
        strategy=strat,
        symbols=symbols,
        priority=10,
        params={"force_decision": "HOLD"},
    )
    sset = StrategySet([entry])

    uni = UniverseRuntime(
        executor=executor,
        market_data=md,
        universe_symbols=symbols,
        strategy_set=sset,
        strategy_priorities={"simple_strategy": 10},
        strategy_weights={"simple_strategy": 1.0},
        router_config=RouterConfig(mode="priority"),
    )

    for _ in range(ticks):
        uni.run_tick()

    assert len(store.fill_events) == len(symbols) * ticks
