from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.base import MarketDataAdapter
from adapters.marketdata.live_market_data import LiveFileMarketData
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.marketdata.simulated_market_data_v2 import SimulatedMarketDataV2
from adapters.storage.datastore_fs import JSONLFileDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from app.universe_runtime import UniverseRuntime
from config.models import RunPlan
from core.signal_router.router import RouterConfig
from strategies.registry import create_strategy
from strategies.strategy_set import StrategyEntry, StrategySet

Env = Literal["live", "sandbox"]


def _call_with_supported_kwargs(fn: Any, /, *args: Any, **kwargs: Any) -> Any:
    sig = inspect.signature(fn)
    filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return fn(*args, **filtered)


def _build_market_data(plan: RunPlan) -> MarketDataAdapter:
    mode = plan.adapters.market_data.mode

    if mode == "live_file":
        if plan.adapters.market_data.prices_path is None:
            raise ValueError("live_file requires prices_path")
        return LiveFileMarketData(Path(plan.adapters.market_data.prices_path))

    if mode == "simulated_v2":
        params = plan.adapters.market_data.params
        seed_raw = params.get("seed", 1)
        seed = int(seed_raw) if isinstance(seed_raw, (int, float)) else 1

        drift_raw = params.get("drift", 0.0)
        drift = float(drift_raw) if isinstance(drift_raw, (int, float)) else 0.0

        vol_raw = params.get("vol", 0.01)
        vol = float(vol_raw) if isinstance(vol_raw, (int, float)) else 0.01

        start = params.get("start_prices", {})
        start_prices: dict[str, float] = {}
        if isinstance(start, dict):
            for k, v in start.items():
                if isinstance(k, str) and isinstance(v, (int, float)):
                    start_prices[k] = float(v)

        # v2 universe needs *_main to match execution instruments
        symbols: list[str] = list(plan.universe.symbols)
        for s in list(symbols):
            if not s.endswith("_main"):
                symbols.append(f"{s}_main")

        return SimulatedMarketDataV2(
            symbols=symbols,
            seed=seed,
            drift=drift,
            vol=vol,
            start_prices=start_prices,
        )

    return SimulatedMarketData()


def _build_strategy_set(plan: RunPlan) -> tuple[StrategySet, dict[str, int], dict[str, float]]:
    entries: list[StrategyEntry] = []
    for s in plan.strategies:
        impl = create_strategy(name=s.name, params=s.params)
        entries.append(
            StrategyEntry(
                name=s.name,
                strategy=impl,
                symbols=list(s.symbols),
                priority=int(s.priority),
                params=dict(s.params),
            )
        )

    priorities = {e.name: e.priority for e in entries}
    weights = {s.name: float(s.weight) for s in plan.strategies}
    return StrategySet(entries), priorities, weights


@dataclass
class UniverseSession:
    env: Env
    runtime_id: str
    executor: Any
    universe: UniverseRuntime
    market_data: MarketDataAdapter
    broker: Any
    datastore: JSONLFileDataStore
    tick: int = 0

    def run_tick(self) -> None:
        self.universe.run_tick()
        self.tick += 1


def build_universe_session(*, plan: RunPlan, env: Env, runtime_id: str) -> UniverseSession:
    store_root = plan.datastore.store_root
    env_root = store_root / env
    env_root.mkdir(parents=True, exist_ok=True)

    market_data = _build_market_data(plan)
    broker = SimulatedBroker(market_data)

    datastore = JSONLFileDataStore(root_dir=env_root, env=env, runtime_id=runtime_id)

    cfg = RuntimeConfig()

    # always create a live runtime for cloning sandbox (if needed)
    live_store = JSONLFileDataStore(root_dir=store_root / "live", env="live", runtime_id=runtime_id)
    live_runtime = _call_with_supported_kwargs(
        RuntimeFactory.build_live_runtime,
        config=cfg,
        runtime_id=runtime_id,
        market_data=market_data,
        broker=broker,
        datastore=live_store,
    )

    if env == "live":
        executor = live_runtime
    else:
        executor = _call_with_supported_kwargs(
            RuntimeFactory.build_sandbox_runtime_from_live,
            live_runtime,
            runtime_id=runtime_id,
            market_data=market_data,
            broker=broker,
            datastore=datastore,
        )

    strategy_set, priorities, weights = _build_strategy_set(plan)
    router_config = RouterConfig(mode=plan.router.mode, tie_breaker=plan.router.tie_breaker)

    universe = UniverseRuntime(
        executor=executor,
        market_data=market_data,
        universe_symbols=list(plan.universe.symbols),
        strategy_set=strategy_set,
        strategy_priorities=priorities,
        strategy_weights=weights,
        router_config=router_config,
    )

    return UniverseSession(
        env=env,
        runtime_id=runtime_id,
        executor=executor,
        universe=universe,
        market_data=market_data,
        broker=broker,
        datastore=datastore,
    )
