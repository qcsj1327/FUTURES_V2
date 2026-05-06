from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

from adapters.broker.base import BrokerAdapter
from adapters.broker.simulated_broker import SimulatedBroker
from adapters.broker.tqkq_adapter import TqKqBrokerAdapter
from adapters.marketdata.base import MarketDataAdapter
from adapters.marketdata.live_market_data import LiveFileMarketData
from adapters.storage.datastore_fs import JSONLFileDataStore
from app.orchestration.spec_artifacts import write_specs_snapshot
from app.orchestration.strategy_switch import load_approved_strategy_map
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from app.universe_runtime import UniverseRuntime
from config.models import RunPlan
from core.instruments.calendar import TradingCalendar, TradingSession
from core.instruments.resolver import InstrumentResolver
from core.instruments.roll_policy import RollPolicy
from core.instruments.spec_provider import StaticSpecProvider, TqKqSpecProvider, deep_merge
from core.instruments.specs import InstrumentSpecRegistry
from core.risk.portfolio_risk_limits import PortfolioRiskLimits
from core.risk.symbol_position_limit import SymbolPositionLimit
from core.signal_router.router import RouterConfig
from strategies.registry import create_strategy
from strategies.strategy_set import StrategyEntry, StrategySet

RuntimeProfile = Literal["local", "dryrun", "live"]


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
        warmup_raw = plan.runtime.warmup_seconds
        if warmup_raw is None:
            warmup_raw = params.get("warmup_seconds", 8.0)
        warmup_seconds = float(warmup_raw) if isinstance(warmup_raw, (int, float)) else 8.0
        md = TqKqMarketData(
            tq_symbols=mapping,
            auth_user=user,
            auth_pass=passwd,
            api_factory=None,
            start_background=True,
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

    if mode == "local_file":
        prices_path = plan.adapters.market_data.prices_path
        if prices_path is None:
            raise ValueError("local_file requires prices_path")
        return LiveFileMarketData(Path(prices_path))

    raise ValueError(f"unsupported market_data mode: {mode}")


def build_broker(plan: RunPlan, market_data: MarketDataAdapter) -> BrokerAdapter:
    return build_broker_with_specs(plan, market_data, instrument_specs=None)


def plan_with_resolved_trade_contracts(
    *,
    plan: RunPlan,
    market_data: MarketDataAdapter,
) -> RunPlan:
    required = bool(plan.instruments.roll_policy.resolve_from_market_data)
    resolver = getattr(market_data, "resolved_trade_symbols", None)
    if not callable(resolver):
        if required:
            raise ValueError(
                "instruments.roll_policy.resolve_from_market_data requires market data "
                "adapter to resolve trade contracts"
            )
        return plan
    contracts = resolver()
    if not isinstance(contracts, dict) or not contracts:
        if required:
            raise ValueError("market data did not resolve any trade contracts")
        return plan
    normalized = {
        symbol: contract
        for symbol, contract in contracts.items()
        if isinstance(symbol, str) and isinstance(contract, str)
    }
    missing = [sym for sym in plan.universe.symbols if sym not in normalized]
    bad_contracts = {
        sym: contract
        for sym, contract in normalized.items()
        if contract.startswith("KQ.") or contract.endswith("_main") or "." not in contract
    }
    if required and missing:
        raise ValueError(f"market data did not resolve trade contracts for symbols: {missing}")
    if required and bad_contracts:
        raise ValueError(f"market data resolved invalid trade contracts: {bad_contracts}")
    if normalized == plan.instruments.roll_policy.contracts and not required:
        return plan
    roll_policy = replace(
        plan.instruments.roll_policy,
        contracts=normalized,
        resolve_from_market_data=False,
    )
    instruments = replace(plan.instruments, roll_policy=roll_policy)
    return replace(plan, instruments=instruments)


def build_broker_with_specs(
    plan: RunPlan,
    market_data: MarketDataAdapter,
    *,
    instrument_specs: InstrumentSpecRegistry | None,
) -> BrokerAdapter:
    if plan.adapters.broker.mode == "tqkq":
        if plan.instruments.roll_policy.mode != "fixed_contract":
            raise ValueError("adapters.broker.mode=tqkq requires fixed_contract roll_policy")
        bad_contracts = {
            sym: contract
            for sym, contract in plan.instruments.roll_policy.contracts.items()
            if contract.startswith("KQ.") or contract.endswith("_main") or "." not in contract
        }
        if bad_contracts:
            raise ValueError(
                "adapters.broker.mode=tqkq requires real trade contracts: "
                f"{bad_contracts}"
            )
        submit_mode = str(plan.adapters.broker.params.get("submit_mode", "dryrun"))
        token = plan.adapters.broker.params.get("confirm_live_token")
        if (
            submit_mode == "live"
            and (
                plan.adapters.broker.params.get("confirm_live") is not True
                or token != plan.runtime.runtime_id
            )
        ):
            raise ValueError(
                "live submit hard gate failed in session_builder: "
                f"submit_mode={submit_mode!r}, "
                f"confirm_live={plan.adapters.broker.params.get('confirm_live') is True}, "
                f"token_present={isinstance(token, str) and bool(token)}, "
                f"expected_token=runtime_id:{plan.runtime.runtime_id}"
            )
        return TqKqBrokerAdapter(
            market_data=market_data,
            instrument_specs=(
                instrument_specs
                or InstrumentSpecRegistry.with_overrides(plan.instruments.specs)
            ),
            dry_run=submit_mode == "dryrun",
        )

    params = plan.adapters.broker.params
    order_id_prefix = str(params.get("order_id_prefix", "LOCAL-SIM"))
    fill_delay_ticks = int(params.get("fill_delay_ticks", 0))
    partial_fill_ratio = float(params.get("partial_fill_ratio", 1.0))
    max_partial_steps = int(params.get("max_partial_steps", 1))
    max_ticks_raw = params.get("max_ticks_to_fill")
    max_ticks_to_fill = int(max_ticks_raw) if max_ticks_raw is not None else None
    no_fill = bool(params.get("no_fill", False))
    return SimulatedBroker(
        market_data,
        order_id_prefix=order_id_prefix,
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
    scope: RuntimeProfile,
    datastore: JSONLFileDataStore,
) -> tuple[TradingCalendar, InstrumentResolver]:
    sessions = (
        {}
        if scope == "local"
        else {
            sym: [TradingSession(start=s.start, end=s.end) for s in items]
            for sym, items in plan.instruments.trading_sessions.items()
        }
    )
    calendar = TradingCalendar(sessions_by_symbol=sessions)
    policy = RollPolicy(
        mode=plan.instruments.roll_policy.mode,
        contracts=dict(plan.instruments.roll_policy.contracts),
        runtime_id=runtime_id,
        scope=scope,
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
    scope: RuntimeProfile
    runtime_id: str
    plan: RunPlan
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


def build_universe_session(
    *,
    plan: RunPlan,
    profile: RuntimeProfile,
    runtime_id: str,
) -> UniverseSession:
    store_root = plan.datastore.store_root
    scope_root = store_root / profile
    scope_root.mkdir(parents=True, exist_ok=True)

    market_data = build_market_data(plan)
    trade_plan = plan_with_resolved_trade_contracts(plan=plan, market_data=market_data)
    instrument_specs = build_instrument_specs_registry(plan=plan, market_data=market_data)
    broker = build_broker_with_specs(trade_plan, market_data, instrument_specs=instrument_specs)

    # Write a deterministic snapshot for audit/replay.
    # One file per runtime_id; safe to overwrite between scoped sessions.
    write_specs_snapshot(
        runtime_id=runtime_id,
        runtime_profile=profile,
        datastore_scope=profile,
        specs=instrument_specs.specs_for(list(plan.universe.symbols)),
        output_dir=plan.datastore.artifacts_root / profile / "specs",
    )

    datastore = JSONLFileDataStore(root_dir=scope_root, scope=profile, runtime_id=runtime_id)
    cfg = RuntimeConfig(
        runtime_id=runtime_id,
        default_quantity=trade_plan.runtime.default_quantity,
        stop_loss=trade_plan.runtime.stop_loss,
        take_profit=trade_plan.runtime.take_profit,
        stop_loss_pct=trade_plan.runtime.stop_loss_pct,
        take_profit_pct=trade_plan.runtime.take_profit_pct,
        dynamic_exit_enabled=trade_plan.runtime.dynamic_exit_enabled,
        dynamic_stop_loss_vol_mult=trade_plan.runtime.dynamic_stop_loss_vol_mult,
        dynamic_take_profit_vol_mult=trade_plan.runtime.dynamic_take_profit_vol_mult,
        dynamic_min_stop_loss_pct=trade_plan.runtime.dynamic_min_stop_loss_pct,
        dynamic_min_take_profit_pct=trade_plan.runtime.dynamic_min_take_profit_pct,
        dynamic_max_stop_loss_pct=trade_plan.runtime.dynamic_max_stop_loss_pct,
        dynamic_max_take_profit_pct=trade_plan.runtime.dynamic_max_take_profit_pct,
    )
    calendar, resolver = build_instrument_services(
        plan=trade_plan,
        runtime_id=runtime_id,
        scope=profile,
        datastore=datastore,
    )

    executor = _call_with_supported_kwargs(
        RuntimeFactory.build_runtime,
        config=cfg,
        runtime_id=runtime_id,
        market_data=market_data,
        broker=broker,
        datastore=datastore,
        scope=profile,
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
    strategy_switch_diagnostics: list[str] = []
    enabled = load_approved_strategy_map(
        runtime_id=runtime_id,
        artifacts_root=plan.datastore.artifacts_root,
        expected_runtime_profile=profile,
        expected_datastore_scope=profile,
        diagnostics=strategy_switch_diagnostics,
    )
    executor.strategy_switch_artifact_diagnostics = strategy_switch_diagnostics
    if enabled is None:
        enabled = dict(plan.strategy_switch.enabled_by_symbol)
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
        scope=profile,
        runtime_id=runtime_id,
        plan=trade_plan,
        executor=executor,
        universe=universe,
        market_data=market_data,
        broker=broker,
        datastore=datastore,
    )
