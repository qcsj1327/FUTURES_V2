from __future__ import annotations

import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from adapters.broker.base import BrokerAdapter
from adapters.broker.simulated_broker import SimulatedBroker
from adapters.broker.tqkq_broker import TqKqBroker
from adapters.broker.tqkq_live_broker import TqKqLiveBroker
from adapters.marketdata.base import MarketDataAdapter
from adapters.marketdata.live_market_data import LiveFileMarketData
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.marketdata.simulated_market_data_v2 import SimulatedMarketDataV2
from adapters.storage.datastore_fs import JSONLFileDataStore
from app.orchestration.strategy_switch import load_approved_strategy_map
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from app.universe_runtime import UniverseRuntime
from config.models import RunPlan
from core.instruments.calendar import TradingCalendar, TradingSession
from core.instruments.resolver import InstrumentResolver
from core.instruments.roll_policy import RollPolicy
from core.instruments.spec_provider import StaticSpecProvider, TqKqSpecProvider, deep_merge
from core.instruments.spec_snapshot import write_specs_snapshot
from core.instruments.specs import InstrumentSpecRegistry
from core.risk.portfolio_risk_limits import PortfolioRiskLimits
from core.risk.symbol_position_limit import SymbolPositionLimit
from core.signal_router.router import RouterConfig
from strategies.registry import create_strategy
from strategies.strategy_set import StrategyEntry, StrategySet

Env = Literal["live", "sandbox"]


@dataclass
class _FakeTqKqQuote:
    last_price: float
    volume: float
    datetime: str
    price_tick: float = 0.2
    volume_multiple: float = 1000.0


class _FakeTqKqApi:
    def __init__(self, *, fake_quotes: dict[str, _FakeTqKqQuote]) -> None:
        self._quotes = fake_quotes

    def get_quote(self, symbol: str) -> _FakeTqKqQuote:
        quote = self._quotes.get(symbol)
        if quote is None:
            raise KeyError(f"fake tqkq quote missing for {symbol}")
        return quote

    def wait_update(self, deadline: float | None = None) -> bool:
        _ = deadline
        for quote in self._quotes.values():
            quote.volume += 1.0
        return True

    def get_account(self) -> dict[str, float]:
        return {"cash": 990000.0, "equity": 1000000.0, "margin_used": 10000.0}

    def get_position(self) -> list[dict[str, object]]:
        return []

    def close(self) -> None:
        return


def _fake_tqkq_quotes(params: dict[str, Any]) -> dict[str, _FakeTqKqQuote] | None:
    raw = params.get("fake_quotes")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("adapters.market_data.params.fake_quotes must be object")
    quotes: dict[str, _FakeTqKqQuote] = {}
    for symbol, payload in raw.items():
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("adapters.market_data.params.fake_quotes keys must be str")
        if not isinstance(payload, dict):
            raise ValueError(f"adapters.market_data.params.fake_quotes.{symbol} must be object")
        price = payload.get("price")
        volume = payload.get("volume", 1000.0)
        ts = payload.get("datetime", "2026-05-04 10:00:00.000000")
        tick = payload.get("price_tick", 0.2)
        multiplier = payload.get("volume_multiple", 1000.0)
        if not isinstance(price, (int, float)) or isinstance(price, bool):
            raise ValueError(
                f"adapters.market_data.params.fake_quotes.{symbol}.price must be number"
            )
        if not isinstance(volume, (int, float)) or isinstance(volume, bool):
            raise ValueError(
                f"adapters.market_data.params.fake_quotes.{symbol}.volume must be number"
            )
        if not isinstance(ts, str):
            raise ValueError(
                f"adapters.market_data.params.fake_quotes.{symbol}.datetime must be str"
            )
        if not isinstance(tick, (int, float)) or isinstance(tick, bool):
            raise ValueError(
                f"adapters.market_data.params.fake_quotes.{symbol}.price_tick must be number"
            )
        if not isinstance(multiplier, (int, float)) or isinstance(multiplier, bool):
            raise ValueError(
                "adapters.market_data.params.fake_quotes."
                f"{symbol}.volume_multiple must be number"
            )
        quotes[symbol] = _FakeTqKqQuote(
            last_price=float(price),
            volume=float(volume),
            datetime=ts,
            price_tick=float(tick),
            volume_multiple=float(multiplier),
        )
    return quotes


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
        fake_quotes = _fake_tqkq_quotes(params)
        user = os.environ.get("TQKQ_USER", "").strip()
        passwd = os.environ.get("TQKQ_PASS", "").strip()
        if fake_quotes is None and (not user or not passwd):
            raise ValueError("TQKQ_USER/TQKQ_PASS must be set in environment")
        from adapters.marketdata.tqkq_market_data import TqKqMarketData
        warmup_raw = plan.runtime.warmup_seconds
        if warmup_raw is None:
            warmup_raw = params.get("warmup_seconds", 8.0)
        warmup_seconds = float(warmup_raw) if isinstance(warmup_raw, (int, float)) else 8.0
        md = TqKqMarketData(
            tq_symbols=mapping,
            auth_user=user,
            auth_pass=passwd,
            api_factory=(
                None
                if fake_quotes is None
                else lambda: _FakeTqKqApi(fake_quotes=fake_quotes)
            ),
            start_background=fake_quotes is None,
        )
        try:
            md.warmup(list(plan.universe.symbols), timeout_s=warmup_seconds)
        except Exception as exc:
            raise ValueError(
                f"tqkq warmup failed: warmup_seconds={warmup_seconds}, "
                f"symbols={list(plan.universe.symbols)}, tq_symbols={mapping}, "
                f"error={exc.__class__.__name__}: {exc}"
            ) from exc
        return md

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


def build_broker(plan: RunPlan, market_data: MarketDataAdapter) -> BrokerAdapter:
    return build_broker_with_specs(plan, market_data, instrument_specs=None)


def build_broker_with_specs(
    plan: RunPlan,
    market_data: MarketDataAdapter,
    *,
    instrument_specs: InstrumentSpecRegistry | None,
) -> BrokerAdapter:
    if plan.adapters.broker.mode == "tqkq_live":
        if plan.instruments.roll_policy.mode != "fixed_contract":
            raise ValueError("adapters.broker.mode=tqkq_live requires fixed_contract roll_policy")
        bad_contracts = {
            sym: contract
            for sym, contract in plan.instruments.roll_policy.contracts.items()
            if contract.endswith("_main") or "." not in contract
        }
        if bad_contracts:
            raise ValueError(
                "adapters.broker.mode=tqkq_live requires real trade contracts: "
                f"{bad_contracts}"
            )
        submit_mode = str(plan.adapters.broker.params.get("submit_mode", "dry_run"))
        token = plan.adapters.broker.params.get("confirm_live_token")
        if (
            submit_mode == "live"
            and (
                plan.adapters.broker.params.get("confirm_live") is not True
                or token != plan.runtime.runtime_id
            )
        ):
            raise ValueError(
                "tqkq_live live submit hard gate failed in session_builder: "
                f"submit_mode={submit_mode!r}, "
                f"confirm_live={plan.adapters.broker.params.get('confirm_live') is True}, "
                f"token_present={isinstance(token, str) and bool(token)}, "
                f"expected_token=runtime_id:{plan.runtime.runtime_id}"
            )
        return TqKqLiveBroker(
            market_data=market_data,
            instrument_specs=(
                instrument_specs
                or InstrumentSpecRegistry.with_overrides(plan.instruments.specs)
            ),
            dry_run=submit_mode == "dry_run",
        )

    if plan.adapters.broker.mode == "tqkq_sim":
        if plan.adapters.market_data.mode != "tqkq":
            raise ValueError(
                "adapters.broker.mode=tqkq_sim requires adapters.market_data.mode=tqkq"
            )
        if plan.instruments.roll_policy.mode != "fixed_contract":
            raise ValueError("adapters.broker.mode=tqkq_sim requires fixed_contract roll_policy")
        bad_contracts = {
            sym: contract
            for sym, contract in plan.instruments.roll_policy.contracts.items()
            if contract.endswith("_main") or "." not in contract
        }
        if bad_contracts:
            raise ValueError(
                "adapters.broker.mode=tqkq_sim requires real trade contracts: "
                f"{bad_contracts}"
            )
        return TqKqBroker(
            market_data=market_data,
            instrument_specs=(
                instrument_specs
                or InstrumentSpecRegistry.with_overrides(plan.instruments.specs)
            ),
            no_fill=bool(plan.adapters.broker.params.get("no_fill", False)),
        )

    params = plan.adapters.broker.params
    fill_delay_ticks = int(params.get("fill_delay_ticks", 0))
    partial_fill_ratio = float(params.get("partial_fill_ratio", 1.0))
    max_partial_steps = int(params.get("max_partial_steps", 1))
    max_ticks_raw = params.get("max_ticks_to_fill")
    max_ticks_to_fill = int(max_ticks_raw) if max_ticks_raw is not None else None
    no_fill = bool(params.get("no_fill", False))
    return SimulatedBroker(
        market_data,
        fill_delay_ticks=fill_delay_ticks,
        partial_fill_ratio=partial_fill_ratio,
        max_partial_steps=max_partial_steps,
        max_ticks_to_fill=max_ticks_to_fill,
        no_fill=no_fill,
        instrument_specs=(
            instrument_specs
            or InstrumentSpecRegistry.with_overrides(plan.instruments.specs)
        ),
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
        close_on_roll=plan.instruments.roll_policy.close_on_roll,
        cooldown_ticks=plan.instruments.roll_policy.cooldown_ticks,
        main_contract_schedule=plan.instruments.roll_policy.main_contract_schedule,
    )
    return calendar, InstrumentResolver(roll_policy=policy)


def build_instrument_specs_registry(
    *,
    plan: RunPlan,
    market_data: MarketDataAdapter,
) -> InstrumentSpecRegistry:
    mode = str(plan.instruments.spec_source)
    plan_overrides = dict(plan.instruments.specs)

    if mode == "tqkq":
        if plan.adapters.market_data.mode != "tqkq":
            raise ValueError("instruments.spec_source=tqkq requires adapters.market_data.mode=tqkq")
        tq_symbols_any = plan.adapters.market_data.params.get("tq_symbols")
        tq_symbols = tq_symbols_any if isinstance(tq_symbols_any, dict) else {}

        def _get_quote(tq_symbol: str) -> object:
            getq = getattr(market_data, "get_quote", None)
            if not callable(getq):
                raise ValueError("tqkq spec_source requires market_data.get_quote(tq_symbol)")
            return getq(tq_symbol)

        provider = TqKqSpecProvider(tq_symbols=tq_symbols, quote_getter=_get_quote)
        auto_overrides = provider.load_overrides(base_symbols=list(plan.universe.symbols))
    else:
        _ = StaticSpecProvider()
        auto_overrides = {}

    final_overrides = deep_merge(auto_overrides, plan_overrides)
    return InstrumentSpecRegistry.with_overrides(final_overrides)


def make_universe_runtime(
    *,
    executor: Any,
    market_data: MarketDataAdapter,
    plan: RunPlan,
    strategy_set: StrategySet,
    priorities: dict[str, int],
    weights: dict[str, float],
    enabled_strategies_by_symbol: dict[str, list[str]] | None = None,
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
        enabled_strategies_by_symbol=enabled_strategies_by_symbol,
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

    def close(self) -> None:
        for resource in (self.broker, self.market_data):
            close = getattr(resource, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass


def build_universe_session(*, plan: RunPlan, env: Env, runtime_id: str) -> UniverseSession:
    store_root = plan.datastore.store_root
    env_root = store_root / env
    env_root.mkdir(parents=True, exist_ok=True)

    market_data = build_market_data(plan)
    instrument_specs = build_instrument_specs_registry(plan=plan, market_data=market_data)
    broker = build_broker_with_specs(plan, market_data, instrument_specs=instrument_specs)

    # Write a deterministic snapshot for audit/replay.
    # (One file per runtime_id; safe to overwrite between env sessions.)
    write_specs_snapshot(
        runtime_id=runtime_id,
        specs=instrument_specs.specs_for(list(plan.universe.symbols)),
        output_dir=plan.datastore.artifacts_root / "specs",
    )

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
    live_runtime.max_pending_ticks = plan.execution.max_pending_ticks
    live_runtime.max_rejects_in_window = plan.execution.max_rejects_in_window
    live_runtime.reject_window_ticks = plan.execution.reject_window_ticks
    live_runtime.halt_ticks = plan.execution.halt_ticks
    live_runtime.min_order_interval_ticks = plan.execution.min_order_interval_ticks
    live_runtime.symbol_position_limit = SymbolPositionLimit(
        plan.risk.max_position_qty_by_symbol
    )
    live_runtime.portfolio_risk_limits = PortfolioRiskLimits(
        max_risk_ratio=plan.risk.max_risk_ratio,
        max_margin_used=plan.risk.max_margin_used,
        max_notional_by_symbol=plan.risk.max_notional_by_symbol,
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
        executor.max_pending_ticks = plan.execution.max_pending_ticks
        executor.max_rejects_in_window = plan.execution.max_rejects_in_window
        executor.reject_window_ticks = plan.execution.reject_window_ticks
        executor.halt_ticks = plan.execution.halt_ticks
        executor.min_order_interval_ticks = plan.execution.min_order_interval_ticks
        executor.symbol_position_limit = SymbolPositionLimit(
            plan.risk.max_position_qty_by_symbol
        )
        executor.portfolio_risk_limits = PortfolioRiskLimits(
            max_risk_ratio=plan.risk.max_risk_ratio,
            max_margin_used=plan.risk.max_margin_used,
            max_notional_by_symbol=plan.risk.max_notional_by_symbol,
        )

    strategy_set, priorities, weights = build_strategy_set(plan)
    enabled = load_approved_strategy_map(
        runtime_id=runtime_id,
        artifacts_root=plan.datastore.artifacts_root,
    )
    universe = make_universe_runtime(
        executor=executor,
        market_data=market_data,
        plan=plan,
        strategy_set=strategy_set,
        priorities=priorities,
        weights=weights,
        enabled_strategies_by_symbol=enabled,
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
