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
from core.instruments.calendar import TradingCalendar, TradingSession
from core.instruments.resolver import InstrumentResolver
from core.instruments.roll_policy import RollPolicy
from core.instruments.specs import InstrumentSpecRegistry
from core.signal_router.router import RouterConfig
from strategies.registry import create_strategy
from strategies.strategy_set import StrategyEntry, StrategySet

Env = Literal["live", "sandbox"]


def _call_with_supported_kwargs(fn: Any, /, *args: Any, **kwargs: Any) -> Any:
    sig = inspect.signature(fn)
    filtered = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return fn(*args, **filtered)


def build_market_data(plan: RunPlan) -> MarketDataAdapter:
    mode = plan.adapters.market_data.mode

    if mode == "tqkq":
        params = plan.adapters.market_data.params
        tq_symbols = params.get("tq_symbols")
        if not isinstance(tq_symbols, dict):
            raise ValueError("tqkq requires params.tq_symbols mapping")
        mapping: dict[str, str] = {}
        for k, v in tq_symbols.items():
            if isinstance(k, str) and isinstance(v, str) and k and v:
                mapping[k] = v
        if not mapping:
            raise ValueError("tqkq requires non-empty tq_symbols mapping")
        import os
        user = os.environ.get("TQKQ_USER", "").strip()
        passwd = os.environ.get("TQKQ_PASS", "").strip()
        if not user or not passwd:
            raise ValueError("TQKQ_USER/TQKQ_PASS must be set in environment")
        from adapters.marketdata.tqkq_market_data import TqKqMarketData
        return TqKqMarketData(tq_symbols=mapping, auth_user=user, auth_pass=passwd)

    if mode == "live_file":
        prices_path = plan.adapters.market_data.prices_path
        if prices_path is None:
            raise ValueError("live_file requires prices_path")
        return LiveFileMarketData(Path(prices_path))

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

        volumes = params.get("start_volumes", {})
        start_volumes: dict[str, float] = {}
        if isinstance(volumes, dict):
            for k, v in volumes.items():
                if isinstance(k, str) and isinstance(v, (int, float)):
                    start_volumes[k] = float(v)

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
            start_volumes=start_volumes,
        )

    return SimulatedMarketData()


def build_broker(plan: RunPlan, market_data: MarketDataAdapter) -> SimulatedBroker:
    params = plan.adapters.broker.params
    fill_delay_ticks = int(params.get("fill_delay_ticks", 0))
    partial_fill_ratio = float(params.get("partial_fill_ratio", 1.0))
    max_ticks_raw = params.get("max_ticks_to_fill")
    max_ticks_to_fill = int(max_ticks_raw) if max_ticks_raw is not None else None
    return SimulatedBroker(
        market_data,
        fill_delay_ticks=fill_delay_ticks,
        partial_fill_ratio=partial_fill_ratio,
        max_ticks_to_fill=max_ticks_to_fill,
        instrument_specs=InstrumentSpecRegistry.with_overrides(plan.instruments.specs),
    )


def build_strategy_set(plan: RunPlan) -> tuple[StrategySet, dict[str, int], dict[str, float]]:
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


def build_instrument_services(
    *,
    plan: RunPlan,
    runtime_id: str,
    env: Env,
    datastore: JSONLFileDataStore,
) -> tuple[TradingCalendar, InstrumentResolver]:
    sessions = {
        sym: [TradingSession(start=s.start, end=s.end) for s in items]
        for sym, items in plan.instruments.trading_sessions.items()
    }
    calendar = TradingCalendar(sessions_by_symbol=sessions)
    policy = RollPolicy(
        mode=plan.instruments.roll_policy.mode,
        contracts=dict(plan.instruments.roll_policy.contracts),
        runtime_id=runtime_id,
        env=env,
        sink=datastore,
    )
    return calendar, InstrumentResolver(roll_policy=policy)


def make_universe_runtime(
    *,
    executor: Any,
    market_data: MarketDataAdapter,
    plan: RunPlan,
    strategy_set: StrategySet,
    priorities: dict[str, int],
    weights: dict[str, float],
) -> UniverseRuntime:
    router_config = RouterConfig(mode=plan.router.mode, tie_breaker=plan.router.tie_breaker)
    return UniverseRuntime(
        executor=executor,
        market_data=market_data,
        universe_symbols=list(plan.universe.symbols),
        strategy_set=strategy_set,
        strategy_priorities=priorities,
        strategy_weights=weights,
        router_config=router_config,
        active_top_n=plan.runtime.active_top_n,
        rank_window=plan.runtime.rank_window,
        rank_metric=plan.runtime.rank_metric,
        rank_refresh_every=plan.runtime.rank_refresh_every,
        rank_emit_events=plan.runtime.rank_emit_events,
    )


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

    market_data = build_market_data(plan)
    broker = build_broker(plan, market_data)

    datastore = JSONLFileDataStore(root_dir=env_root, env=env, runtime_id=runtime_id)
    cfg = RuntimeConfig()
    calendar, resolver = build_instrument_services(
        plan=plan,
        runtime_id=runtime_id,
        env=env,
        datastore=datastore,
    )

    live_store = JSONLFileDataStore(
        root_dir=store_root / "live",
        env="live",
        runtime_id=runtime_id,
    )
    live_runtime = _call_with_supported_kwargs(
        RuntimeFactory.build_live_runtime,
        config=cfg,
        runtime_id=runtime_id,
        market_data=market_data,
        broker=broker,
        datastore=live_store,
        trading_calendar=calendar,
        instrument_resolver=resolver,
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
            trading_calendar=calendar,
            instrument_resolver=resolver,
        )

    strategy_set, priorities, weights = build_strategy_set(plan)
    universe = make_universe_runtime(
        executor=executor,
        market_data=market_data,
        plan=plan,
        strategy_set=strategy_set,
        priorities=priorities,
        weights=weights,
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
