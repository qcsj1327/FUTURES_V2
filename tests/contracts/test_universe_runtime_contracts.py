from __future__ import annotations

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_memory import MemoryDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from app.universe_runtime import UniverseRuntime
from strategies.base.simple_strategy import StrategyEngine
from strategies.strategy_set import StrategyEntry, StrategySet


def test_universe_runtime_runs_two_symbols_two_ticks_and_writes_events() -> None:
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

    entries = [
        StrategyEntry(
            name="s1",
            strategy=StrategyEngine(),
            symbols=["au", "ag"],
            priority=10,
            params={},
        ),
    ]
    sset = StrategySet(entries)

    uni = UniverseRuntime(
        executor=executor,
        market_data=md,
        universe_symbols=["au", "ag"],
        strategy_set=sset,
        strategy_priorities={"s1": 10},
    )

    uni.run_tick()
    uni.run_tick()

    # 2 symbols routed -> 2 execution events per tick -> 4 total
    assert len(store.fill_events) == 4
