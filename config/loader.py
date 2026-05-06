from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal, cast

from config.defaults import default_plan
from config.instrument_universe import (
    main_quotes_for,
    trade_contracts_for,
)
from config.models import (
    AdaptersSpec,
    BrokerSpec,
    DataStoreSpec,
    ExecutionSpec,
    InstrumentsSpec,
    MarketDataSpec,
    PromotionSpec,
    RiskSpec,
    RollPolicySpec,
    RouterSpec,
    RunPlan,
    RuntimeSpec,
    StrategySpec,
    StrategySwitchSpec,
    TradingSessionSpec,
    UniverseSpec,
)

RuntimeMode = Literal["local", "dryrun", "live"]


def _assert_keys(obj: dict[str, Any], allowed: set[str], *, where: str) -> None:
    extra = set(obj.keys()) - allowed
    if extra:
        raise ValueError(f"unknown keys at {where}: {sorted(extra)}")


def load_plan(path: Path | None, *, runtime_id: str) -> RunPlan:
    base = default_plan(runtime_id=runtime_id)

    if path is None:
        return base

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("plan must be a json object")

    _assert_keys(
        raw,
        {
            "schema_version",
            "env",
            "universe",
            "strategies",
            "runtime",
            "datastore",
            "promotion",
            "router",
            "strategy_switch",
            "adapters",
            "instruments",
            "execution",
            "risk",
        },
        where="root",
    )

    if raw.get("schema_version") != 1:
        raise ValueError("unsupported schema_version")

    base_dir = (path.parent if path is not None else Path.cwd())

    env = raw.get("env", base.env)

    # universe
    universe_raw = raw.get("universe", {})
    if not isinstance(universe_raw, dict):
        raise ValueError("universe must be an object")
    _assert_keys(universe_raw, {"symbols"}, where="universe")
    symbols = universe_raw.get("symbols", asdict(base.universe)["symbols"])
    if not isinstance(symbols, list) or not all(isinstance(s, str) for s in symbols):
        raise ValueError("universe.symbols must be list[str]")
    if any(s.endswith("_main") for s in symbols):
        raise ValueError("universe.symbols must use base symbols")
    universe = UniverseSpec(symbols=list(symbols))

    # strategies
    strategies_raw = raw.get("strategies", [])
    if not isinstance(strategies_raw, list):
        raise ValueError("strategies must be a list")
    strategies: list[StrategySpec] = []
    for i, sraw in enumerate(strategies_raw):
        if not isinstance(sraw, dict):
            raise ValueError(f"strategy[{i}] must be an object")
        _assert_keys(
            sraw,
            {"name", "params", "symbols", "priority", "weight"},
            where=f"strategy[{i}]",
        )
        name = sraw.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"strategy[{i}].name required")
        params = sraw.get("params", {})
        if not isinstance(params, dict):
            raise ValueError(f"strategy[{i}].params must be object")
        ss = sraw.get("symbols", universe.symbols)
        if not isinstance(ss, list) or not all(isinstance(x, str) for x in ss):
            raise ValueError(f"strategy[{i}].symbols must be list[str]")
        if any(x.endswith("_main") for x in ss):
            raise ValueError(f"strategy[{i}].symbols must use base symbols")
        priority = sraw.get("priority", 100)
        weight = sraw.get("weight", 1.0)
        strategies.append(
            StrategySpec(
                name=name,
                params=dict(params),
                symbols=list(ss),
                priority=int(priority),
                weight=float(weight),
            )
        )
    if not strategies:
        strategies = list(base.strategies)

    strategy_switch_raw = raw.get("strategy_switch", {})
    if not isinstance(strategy_switch_raw, dict):
        raise ValueError("strategy_switch must be an object")
    _assert_keys(
        strategy_switch_raw,
        {
            "enabled_by_symbol",
            "approval_required",
            "min_score",
            "max_enabled_strategies_per_symbol",
        },
        where="strategy_switch",
    )
    configured_strategy_names = {strategy.name for strategy in strategies}
    enabled_raw = strategy_switch_raw.get("enabled_by_symbol")
    if enabled_raw is None:
        enabled_by_symbol = _default_enabled_by_symbol(strategies, list(universe.symbols))
    else:
        if not isinstance(enabled_raw, dict):
            raise ValueError("strategy_switch.enabled_by_symbol must be object")
        enabled_by_symbol = _parse_enabled_by_symbol(
            enabled_raw,
            universe_symbols=list(universe.symbols),
            strategy_names=configured_strategy_names,
        )
    max_enabled = int(
        strategy_switch_raw.get(
            "max_enabled_strategies_per_symbol",
            base.strategy_switch.max_enabled_strategies_per_symbol,
        )
    )
    if max_enabled <= 0:
        raise ValueError("strategy_switch.max_enabled_strategies_per_symbol must be positive")
    for sym, names in enabled_by_symbol.items():
        if len(names) > max_enabled:
            raise ValueError(
                "strategy_switch.enabled_by_symbol exceeds "
                f"max_enabled_strategies_per_symbol for {sym}"
            )
    strategy_switch = StrategySwitchSpec(
        enabled_by_symbol=enabled_by_symbol,
        approval_required=bool(
            strategy_switch_raw.get(
                "approval_required",
                base.strategy_switch.approval_required,
            )
        ),
        min_score=float(
            strategy_switch_raw.get("min_score", base.strategy_switch.min_score)
        ),
        max_enabled_strategies_per_symbol=max_enabled,
    )

    # runtime (runtime_id is always overridden by function arg)
    runtime_raw = raw.get("runtime", {})
    if not isinstance(runtime_raw, dict):
        raise ValueError("runtime must be an object")
    _assert_keys(
        runtime_raw,
        {
            "mode",
            "warmup_seconds",
            "ticks_live",
            "ticks_dryrun",
            "default_quantity",
            "stop_loss",
            "take_profit",
            "stop_loss_pct",
            "take_profit_pct",
            "dynamic_exit_enabled",
            "dynamic_stop_loss_vol_mult",
            "dynamic_take_profit_vol_mult",
            "dynamic_min_stop_loss_pct",
            "dynamic_min_take_profit_pct",
            "dynamic_max_stop_loss_pct",
            "dynamic_max_take_profit_pct",
            "active_top_n",
            "rank_window",
            "rank_metric",
            "rank_refresh_every",
            "rank_emit_events",
        },
        where="runtime",
    )
    runtime_mode_raw = str(runtime_raw.get("mode", base.runtime.mode))
    if runtime_mode_raw not in {"local", "dryrun", "live"}:
        raise ValueError(f"invalid runtime.mode: {runtime_mode_raw}")
    runtime_mode = cast(RuntimeMode, runtime_mode_raw)
    warmup_raw = runtime_raw.get("warmup_seconds", base.runtime.warmup_seconds)
    warmup_seconds = None if warmup_raw is None else float(warmup_raw)
    ticks_live = int(runtime_raw.get("ticks_live", base.runtime.ticks_live))
    ticks_dryrun = int(runtime_raw.get("ticks_dryrun", base.runtime.ticks_dryrun))
    default_quantity = float(runtime_raw.get("default_quantity", base.runtime.default_quantity))
    stop_loss = runtime_raw.get("stop_loss", base.runtime.stop_loss)
    take_profit = runtime_raw.get("take_profit", base.runtime.take_profit)
    stop_loss_pct = runtime_raw.get("stop_loss_pct", base.runtime.stop_loss_pct)
    take_profit_pct = runtime_raw.get("take_profit_pct", base.runtime.take_profit_pct)
    dynamic_exit_enabled = bool(
        runtime_raw.get("dynamic_exit_enabled", base.runtime.dynamic_exit_enabled)
    )
    dynamic_stop_loss_vol_mult = float(
        runtime_raw.get(
            "dynamic_stop_loss_vol_mult",
            base.runtime.dynamic_stop_loss_vol_mult,
        )
    )
    dynamic_take_profit_vol_mult = float(
        runtime_raw.get(
            "dynamic_take_profit_vol_mult",
            base.runtime.dynamic_take_profit_vol_mult,
        )
    )
    dynamic_min_stop_loss_pct = float(
        runtime_raw.get(
            "dynamic_min_stop_loss_pct",
            base.runtime.dynamic_min_stop_loss_pct,
        )
    )
    dynamic_min_take_profit_pct = float(
        runtime_raw.get(
            "dynamic_min_take_profit_pct",
            base.runtime.dynamic_min_take_profit_pct,
        )
    )
    dynamic_max_stop_loss_pct = float(
        runtime_raw.get(
            "dynamic_max_stop_loss_pct",
            base.runtime.dynamic_max_stop_loss_pct,
        )
    )
    dynamic_max_take_profit_pct = float(
        runtime_raw.get(
            "dynamic_max_take_profit_pct",
            base.runtime.dynamic_max_take_profit_pct,
        )
    )
    active_top_n = int(runtime_raw.get("active_top_n", base.runtime.active_top_n))
    rank_window = int(runtime_raw.get("rank_window", base.runtime.rank_window))
    rank_metric = str(runtime_raw.get("rank_metric", base.runtime.rank_metric))
    rank_refresh_every = int(runtime_raw.get("rank_refresh_every", base.runtime.rank_refresh_every))
    rank_emit_events = int(runtime_raw.get("rank_emit_events", base.runtime.rank_emit_events))
    if active_top_n < 0:
        raise ValueError("runtime.active_top_n must be >= 0")
    if rank_window < 1:
        raise ValueError("runtime.rank_window must be >= 1")
    if rank_metric not in {"signal_strength", "quote_momentum_volume"}:
        raise ValueError("runtime.rank_metric must be signal_strength or quote_momentum_volume")
    if rank_refresh_every < 1:
        raise ValueError("runtime.rank_refresh_every must be >= 1")
    if rank_emit_events not in {0, 1}:
        raise ValueError("runtime.rank_emit_events must be 0 or 1")
    if stop_loss_pct is not None and float(stop_loss_pct) < 0:
        raise ValueError("runtime.stop_loss_pct must be >= 0")
    if take_profit_pct is not None and float(take_profit_pct) < 0:
        raise ValueError("runtime.take_profit_pct must be >= 0")
    dynamic_values = {
        "dynamic_stop_loss_vol_mult": dynamic_stop_loss_vol_mult,
        "dynamic_take_profit_vol_mult": dynamic_take_profit_vol_mult,
        "dynamic_min_stop_loss_pct": dynamic_min_stop_loss_pct,
        "dynamic_min_take_profit_pct": dynamic_min_take_profit_pct,
        "dynamic_max_stop_loss_pct": dynamic_max_stop_loss_pct,
        "dynamic_max_take_profit_pct": dynamic_max_take_profit_pct,
    }
    for key, value in dynamic_values.items():
        if value < 0:
            raise ValueError(f"runtime.{key} must be >= 0")
    if dynamic_min_stop_loss_pct > dynamic_max_stop_loss_pct:
        raise ValueError("runtime.dynamic_min_stop_loss_pct must be <= dynamic_max_stop_loss_pct")
    if dynamic_min_take_profit_pct > dynamic_max_take_profit_pct:
        raise ValueError(
            "runtime.dynamic_min_take_profit_pct must be <= dynamic_max_take_profit_pct"
        )
    runtime = RuntimeSpec(
        runtime_id=runtime_id,
        ticks_live=ticks_live,
        ticks_dryrun=ticks_dryrun,
        default_quantity=default_quantity,
        mode=runtime_mode,
        warmup_seconds=warmup_seconds,
        stop_loss=stop_loss if stop_loss is None else float(stop_loss),
        take_profit=take_profit if take_profit is None else float(take_profit),
        stop_loss_pct=stop_loss_pct if stop_loss_pct is None else float(stop_loss_pct),
        take_profit_pct=take_profit_pct if take_profit_pct is None else float(take_profit_pct),
        dynamic_exit_enabled=dynamic_exit_enabled,
        dynamic_stop_loss_vol_mult=dynamic_stop_loss_vol_mult,
        dynamic_take_profit_vol_mult=dynamic_take_profit_vol_mult,
        dynamic_min_stop_loss_pct=dynamic_min_stop_loss_pct,
        dynamic_min_take_profit_pct=dynamic_min_take_profit_pct,
        dynamic_max_stop_loss_pct=dynamic_max_stop_loss_pct,
        dynamic_max_take_profit_pct=dynamic_max_take_profit_pct,
        active_top_n=active_top_n,
        rank_window=rank_window,
        rank_metric=rank_metric,
        rank_refresh_every=rank_refresh_every,
        rank_emit_events=rank_emit_events,
    )

    # datastore (optional override paths)
    ds_raw = raw.get("datastore", {})
    if not isinstance(ds_raw, dict):
        raise ValueError("datastore must be an object")
    _assert_keys(
        ds_raw,
        {
            "store_root",
            "artifacts_root",
            "approved_dir",
            "decisions_dir",
            "summaries_dir",
            "manifests_dir",
        },
        where="datastore",
    )

    def _p(key: str, default: Path) -> Path:
        v = ds_raw.get(key)
        if v is None:
            return default
        if not isinstance(v, str):
            raise ValueError(f"datastore.{key} must be str path")
        pp = Path(v).expanduser()
        if pp.is_absolute():
            return pp
        return (base_dir / pp).resolve()

    datastore = DataStoreSpec(
        store_root=_p("store_root", base.datastore.store_root),
        artifacts_root=_p("artifacts_root", base.datastore.artifacts_root),
        approved_dir=_p("approved_dir", base.datastore.approved_dir),
        decisions_dir=_p("decisions_dir", base.datastore.decisions_dir),
        summaries_dir=_p("summaries_dir", base.datastore.summaries_dir),
        manifests_dir=_p("manifests_dir", base.datastore.manifests_dir),
    )

    # promotion
    promo_raw = raw.get("promotion", {})
    if not isinstance(promo_raw, dict):
        raise ValueError("promotion must be an object")
    _assert_keys(
        promo_raw,
        {
            "min_events",
            "min_success_rate_improvement",
            "max_consecutive_failures",
            "write_summary",
            "write_decision",
            "write_manifest",
            "write_approved",
        },
        where="promotion",
    )
    promotion = PromotionSpec(
        min_events=int(promo_raw.get("min_events", base.promotion.min_events)),
        min_success_rate_improvement=float(
            promo_raw.get(
                "min_success_rate_improvement",
                base.promotion.min_success_rate_improvement,
            )
        ),
        max_consecutive_failures=int(
            promo_raw.get(
                "max_consecutive_failures",
                base.promotion.max_consecutive_failures,
            )
        ),
        write_summary=bool(promo_raw.get("write_summary", base.promotion.write_summary)),
        write_decision=bool(promo_raw.get("write_decision", base.promotion.write_decision)),
        write_manifest=bool(promo_raw.get("write_manifest", base.promotion.write_manifest)),
        write_approved=bool(promo_raw.get("write_approved", base.promotion.write_approved)),
    )

    execution_raw = raw.get("execution", {})
    if not isinstance(execution_raw, dict):
        raise ValueError("execution must be an object")
    _assert_keys(
        execution_raw,
        {
            "max_pending_ticks",
            "max_rejects_in_window",
            "reject_window_ticks",
            "halt_ticks",
            "min_order_interval_ticks",
        },
        where="execution",
    )
    max_pending_raw = execution_raw.get(
        "max_pending_ticks",
        base.execution.max_pending_ticks,
    )
    max_pending_ticks = None if max_pending_raw is None else int(max_pending_raw)
    if max_pending_ticks is not None and max_pending_ticks < 1:
        raise ValueError("execution.max_pending_ticks must be >= 1")
    max_rejects_raw = execution_raw.get(
        "max_rejects_in_window",
        base.execution.max_rejects_in_window,
    )
    max_rejects_in_window = None if max_rejects_raw is None else int(max_rejects_raw)
    if max_rejects_in_window is not None and max_rejects_in_window < 1:
        raise ValueError("execution.max_rejects_in_window must be >= 1")
    reject_window_raw = execution_raw.get(
        "reject_window_ticks",
        base.execution.reject_window_ticks,
    )
    reject_window_ticks = None if reject_window_raw is None else int(reject_window_raw)
    if reject_window_ticks is not None and reject_window_ticks < 1:
        raise ValueError("execution.reject_window_ticks must be >= 1")
    halt_ticks_raw = execution_raw.get("halt_ticks", base.execution.halt_ticks)
    halt_ticks = None if halt_ticks_raw is None else int(halt_ticks_raw)
    if halt_ticks is not None and halt_ticks < 1:
        raise ValueError("execution.halt_ticks must be >= 1")
    interval_raw = execution_raw.get(
        "min_order_interval_ticks",
        base.execution.min_order_interval_ticks,
    )
    min_order_interval_ticks = None if interval_raw is None else int(interval_raw)
    if min_order_interval_ticks is not None and min_order_interval_ticks < 1:
        raise ValueError("execution.min_order_interval_ticks must be >= 1")
    execution = ExecutionSpec(
        max_pending_ticks=max_pending_ticks,
        max_rejects_in_window=max_rejects_in_window,
        reject_window_ticks=reject_window_ticks,
        halt_ticks=halt_ticks,
        min_order_interval_ticks=min_order_interval_ticks,
    )

    risk_raw = raw.get("risk", {})
    if not isinstance(risk_raw, dict):
        raise ValueError("risk must be an object")
    _assert_keys(
        risk_raw,
        {
            "max_position_qty_by_symbol",
            "max_risk_ratio",
            "max_margin_used",
            "max_notional_by_symbol",
        },
        where="risk",
    )
    limits_raw = risk_raw.get(
        "max_position_qty_by_symbol",
        base.risk.max_position_qty_by_symbol,
    )
    if not isinstance(limits_raw, dict):
        raise ValueError("risk.max_position_qty_by_symbol must be object")
    max_position_qty_by_symbol: dict[str, float] = {}
    for sym, value in limits_raw.items():
        if not isinstance(sym, str) or not sym or sym.endswith("_main"):
            raise ValueError("risk.max_position_qty_by_symbol keys must be base symbols")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"risk.max_position_qty_by_symbol.{sym} must be number")
        qty = float(value)
        if qty < 0:
            raise ValueError(f"risk.max_position_qty_by_symbol.{sym} must be >= 0")
        max_position_qty_by_symbol[sym] = qty
    max_risk_ratio_raw = risk_raw.get("max_risk_ratio", base.risk.max_risk_ratio)
    if isinstance(max_risk_ratio_raw, bool):
        raise ValueError("risk.max_risk_ratio must be number")
    max_risk_ratio = None if max_risk_ratio_raw is None else float(max_risk_ratio_raw)
    if max_risk_ratio is not None and max_risk_ratio < 0:
        raise ValueError("risk.max_risk_ratio must be >= 0")
    max_margin_used_raw = risk_raw.get("max_margin_used", base.risk.max_margin_used)
    if isinstance(max_margin_used_raw, bool):
        raise ValueError("risk.max_margin_used must be number")
    max_margin_used = None if max_margin_used_raw is None else float(max_margin_used_raw)
    if max_margin_used is not None and max_margin_used < 0:
        raise ValueError("risk.max_margin_used must be >= 0")

    notional_raw = risk_raw.get(
        "max_notional_by_symbol",
        base.risk.max_notional_by_symbol,
    )
    if not isinstance(notional_raw, dict):
        raise ValueError("risk.max_notional_by_symbol must be object")
    max_notional_by_symbol: dict[str, float] = {}
    for sym, value in notional_raw.items():
        if not isinstance(sym, str) or not sym or sym.endswith("_main"):
            raise ValueError("risk.max_notional_by_symbol keys must be base symbols")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"risk.max_notional_by_symbol.{sym} must be number")
        notional = float(value)
        if notional < 0:
            raise ValueError(f"risk.max_notional_by_symbol.{sym} must be >= 0")
        max_notional_by_symbol[sym] = notional
    risk = RiskSpec(
        max_position_qty_by_symbol=max_position_qty_by_symbol,
        max_risk_ratio=max_risk_ratio,
        max_margin_used=max_margin_used,
        max_notional_by_symbol=max_notional_by_symbol,
    )

    # router
    router_raw = raw.get("router", {})
    if not isinstance(router_raw, dict):
        raise ValueError("router must be an object")
    _assert_keys(router_raw, {"mode", "tie_breaker"}, where="router")
    router = RouterSpec(
        mode=str(router_raw.get("mode", base.router.mode)),
        tie_breaker=str(router_raw.get("tie_breaker", base.router.tie_breaker)),
    )

    allowed_router_modes = {"priority", "weighted_vote", "netting"}
    allowed_tie_breakers = {"priority", "lex"}
    if router.mode not in allowed_router_modes:
        raise ValueError(f"invalid router.mode: {router.mode}")
    if router.tie_breaker not in allowed_tie_breakers:
        raise ValueError(f"invalid router.tie_breaker: {router.tie_breaker}")

    instruments_raw = raw.get("instruments", {})
    if not isinstance(instruments_raw, dict):
        raise ValueError("instruments must be an object")
    _assert_keys(
        instruments_raw,
        {"trading_sessions", "roll_policy", "spec_source", "specs"},
        where="instruments",
    )

    sessions_raw = instruments_raw.get("trading_sessions", {})
    if not isinstance(sessions_raw, dict):
        raise ValueError("instruments.trading_sessions must be object")
    trading_sessions: dict[str, list[TradingSessionSpec]] = {}
    for sym, sessions in sessions_raw.items():
        if not isinstance(sym, str) or sym.endswith("_main"):
            raise ValueError("instruments.trading_sessions keys must be base symbols")
        if not isinstance(sessions, list):
            raise ValueError(f"instruments.trading_sessions.{sym} must be list")
        parsed_sessions: list[TradingSessionSpec] = []
        for i, session in enumerate(sessions):
            if not isinstance(session, dict):
                raise ValueError(f"instruments.trading_sessions.{sym}[{i}] must be object")
            _assert_keys(
                session,
                {"start", "end"},
                where=f"instruments.trading_sessions.{sym}[{i}]",
            )
            start = session.get("start")
            end = session.get("end")
            if not isinstance(start, str) or not isinstance(end, str):
                raise ValueError(f"instruments.trading_sessions.{sym}[{i}] start/end required")
            parsed_sessions.append(TradingSessionSpec(start=start, end=end))
        trading_sessions[sym] = parsed_sessions
    if not trading_sessions:
        trading_sessions = dict(base.instruments.trading_sessions)

    roll_raw = instruments_raw.get("roll_policy", {})
    if not isinstance(roll_raw, dict):
        raise ValueError("instruments.roll_policy must be object")
    _assert_keys(
        roll_raw,
        {
            "mode",
            "contracts",
            "resolve_from_market_data",
            "close_on_roll",
            "cooldown_ticks",
            "main_contract_schedule",
        },
        where="instruments.roll_policy",
    )
    roll_mode = str(roll_raw.get("mode", base.instruments.roll_policy.mode))
    if roll_mode not in {"fixed_contract", "fixed_main"}:
        raise ValueError(f"invalid instruments.roll_policy.mode: {roll_mode}")
    resolve_from_market_data_raw = roll_raw.get(
        "resolve_from_market_data",
        base.instruments.roll_policy.resolve_from_market_data,
    )
    if not isinstance(resolve_from_market_data_raw, bool):
        raise ValueError("instruments.roll_policy.resolve_from_market_data must be bool")
    resolve_from_market_data = resolve_from_market_data_raw
    contracts_raw = (
        {}
        if resolve_from_market_data
        else roll_raw.get("contracts", trade_contracts_for(list(universe.symbols)))
    )
    if not isinstance(contracts_raw, dict):
        raise ValueError("instruments.roll_policy.contracts must be object")
    contracts: dict[str, str] = {}
    for sym, contract in contracts_raw.items():
        if not isinstance(sym, str) or sym.endswith("_main"):
            raise ValueError("instruments.roll_policy.contracts keys must be base symbols")
        if not isinstance(contract, str) or not contract:
            raise ValueError(f"instruments.roll_policy.contracts.{sym} must be non-empty str")
        contracts[sym] = contract
    if resolve_from_market_data and roll_mode != "fixed_contract":
        raise ValueError(
            "instruments.roll_policy.resolve_from_market_data requires mode=fixed_contract"
        )
    if not resolve_from_market_data:
        for sym in universe.symbols:
            if sym not in contracts:
                raise ValueError(f"missing instruments.roll_policy.contracts.{sym}")
    close_on_roll_raw = roll_raw.get(
        "close_on_roll",
        base.instruments.roll_policy.close_on_roll,
    )
    if not isinstance(close_on_roll_raw, bool):
        raise ValueError("instruments.roll_policy.close_on_roll must be bool")
    close_on_roll = close_on_roll_raw
    cooldown_raw = roll_raw.get(
        "cooldown_ticks",
        base.instruments.roll_policy.cooldown_ticks,
    )
    if not isinstance(cooldown_raw, int) or isinstance(cooldown_raw, bool):
        raise ValueError("instruments.roll_policy.cooldown_ticks must be int")
    cooldown_ticks = int(cooldown_raw)
    if cooldown_ticks < 0:
        raise ValueError("instruments.roll_policy.cooldown_ticks must be >= 0")
    if close_on_roll and roll_mode != "fixed_main":
        raise ValueError("instruments.roll_policy.close_on_roll requires mode=fixed_main")
    if close_on_roll and cooldown_ticks <= 0:
        raise ValueError(
            "instruments.roll_policy.cooldown_ticks must be > 0 when close_on_roll=true"
        )
    schedule_raw = roll_raw.get(
        "main_contract_schedule",
        base.instruments.roll_policy.main_contract_schedule,
    )
    if not isinstance(schedule_raw, dict):
        raise ValueError("instruments.roll_policy.main_contract_schedule must be object")
    main_contract_schedule: dict[str, list[str]] = {}
    for sym, values in schedule_raw.items():
        if not isinstance(sym, str) or sym.endswith("_main"):
            raise ValueError(
                "instruments.roll_policy.main_contract_schedule keys must be base symbols"
            )
        if not isinstance(values, list) or not values:
            raise ValueError(
                f"instruments.roll_policy.main_contract_schedule.{sym} must be non-empty list"
            )
        parsed: list[str] = []
        for i, value in enumerate(values):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    "instruments.roll_policy.main_contract_schedule."
                    f"{sym}[{i}] must be non-empty str"
                )
            parsed.append(value)
        main_contract_schedule[sym] = parsed

    spec_source = str(instruments_raw.get("spec_source", base.instruments.spec_source))
    if spec_source not in {"static", "tqkq"}:
        raise ValueError("instruments.spec_source must be static or tqkq")
    spec_source_typed = cast(Literal["static", "tqkq"], spec_source)

    specs_raw = instruments_raw.get("specs", {})
    if not isinstance(specs_raw, dict):
        raise ValueError("instruments.specs must be object")
    specs: dict[str, dict[str, Any]] = {}
    for sym, spec in specs_raw.items():
        if not isinstance(sym, str) or sym.endswith("_main"):
            raise ValueError("instruments.specs keys must be base symbols")
        if not isinstance(spec, dict):
            raise ValueError(f"instruments.specs.{sym} must be object")
        specs[sym] = dict(spec)
    instruments = InstrumentsSpec(
        trading_sessions=trading_sessions,
        roll_policy=RollPolicySpec(
            mode=roll_mode,
            contracts=contracts,
            resolve_from_market_data=resolve_from_market_data,
            close_on_roll=close_on_roll,
            cooldown_ticks=cooldown_ticks,
            main_contract_schedule=main_contract_schedule,
        ),
        spec_source=spec_source_typed,
        specs=specs,
    )

    # adapters
    adapters_raw = raw.get("adapters", {})
    if not isinstance(adapters_raw, dict):
        raise ValueError("adapters must be an object")
    _assert_keys(adapters_raw, {"market_data", "broker"}, where="adapters")

    md_raw = adapters_raw.get("market_data", {})
    if not isinstance(md_raw, dict):
        raise ValueError("adapters.market_data must be an object")
    _assert_keys(md_raw, {"mode", "prices_path", "params"}, where="adapters.market_data")

    md_mode = str(md_raw.get("mode", base.adapters.market_data.mode))
    md_mode_explicit = "mode" in md_raw
    md_params = md_raw.get("params", {})
    if not isinstance(md_params, dict):
        raise ValueError("adapters.market_data.params must be object")
    prices_path = md_raw.get("prices_path", None)
    # resolve prices_path relative to plan file dir (not cwd)
    if isinstance(prices_path, str):
        pp = Path(prices_path).expanduser()
        if not pp.is_absolute():
            prices_path = str((base_dir / pp).resolve())
        else:
            prices_path = str(pp)
    if prices_path is not None and not isinstance(prices_path, str):
        raise ValueError("adapters.market_data.prices_path must be str")
    if md_mode not in {"local_file", "tqkq"}:
        raise ValueError(f"invalid adapters.market_data.mode: {md_mode}")

    adapters = AdaptersSpec(
        market_data=MarketDataSpec(
            mode=cast(Literal["local_file", "tqkq"], md_mode),
            prices_path=prices_path,
            params=dict(md_params),
        ),
        broker=BrokerSpec(),
    )

    broker_raw = adapters_raw.get("broker", {})
    if not isinstance(broker_raw, dict):
        raise ValueError("adapters.broker must be an object")
    _assert_keys(broker_raw, {"mode", "params"}, where="adapters.broker")
    broker_mode = str(broker_raw.get("mode", "simulated"))
    broker_mode_explicit = "mode" in broker_raw
    if broker_mode not in {"simulated", "tqkq"}:
        raise ValueError(f"invalid adapters.broker.mode: {broker_mode}")
    broker_params = broker_raw.get("params", {})
    if not isinstance(broker_params, dict):
        raise ValueError("adapters.broker.params must be object")
    _validate_broker_params(
        broker_mode=broker_mode,
        params=broker_params,
        runtime_id=runtime_id,
    )
    runtime, adapters, instruments = _normalize_runtime_mode(
        runtime=runtime,
        md_mode=md_mode,
        md_mode_explicit=md_mode_explicit,
        prices_path=prices_path,
        md_params=dict(md_params),
        broker_mode=broker_mode,
        broker_mode_explicit=broker_mode_explicit,
        broker_params=dict(broker_params),
        instruments=instruments,
        spec_source_explicit="spec_source" in instruments_raw,
        universe_symbols=list(universe.symbols),
        base_dir=base_dir,
    )

    return RunPlan(
        schema_version=1,
        env=env,
        universe=universe,
        strategies=strategies,
        adapters=adapters,
        runtime=runtime,
        datastore=datastore,
        promotion=promotion,
        router=router,
        strategy_switch=strategy_switch,
        execution=execution,
        risk=risk,
        instruments=instruments,
    )


def _default_enabled_by_symbol(
    strategies: list[StrategySpec],
    universe_symbols: list[str],
) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for symbol in universe_symbols:
        for strategy in sorted(strategies, key=lambda s: (s.priority, s.name)):
            if symbol in strategy.symbols:
                out[symbol] = [strategy.name]
                break
    return out


def _parse_enabled_by_symbol(
    raw: dict[str, Any],
    *,
    universe_symbols: list[str],
    strategy_names: set[str],
) -> dict[str, list[str]]:
    universe = set(universe_symbols)
    out: dict[str, list[str]] = {}
    for sym, names in raw.items():
        if not isinstance(sym, str) or sym not in universe:
            raise ValueError("strategy_switch.enabled_by_symbol keys must be universe symbols")
        if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
            raise ValueError("strategy_switch.enabled_by_symbol values must be list[str]")
        unknown = [name for name in names if name not in strategy_names]
        if unknown:
            raise ValueError(
                f"strategy_switch.enabled_by_symbol references unknown strategies: {unknown}"
            )
        parsed = sorted(set(names))
        if parsed:
            out[sym] = parsed
    return out


def _normalize_runtime_mode(
    *,
    runtime: RuntimeSpec,
    md_mode: str,
    md_mode_explicit: bool,
    prices_path: str | None,
    md_params: dict[str, Any],
    broker_mode: str,
    broker_mode_explicit: bool,
    broker_params: dict[str, Any],
    instruments: InstrumentsSpec,
    spec_source_explicit: bool,
    universe_symbols: list[str],
    base_dir: Path,
) -> tuple[RuntimeSpec, AdaptersSpec, InstrumentsSpec]:
    mode = runtime.mode
    expected_md = "local_file" if mode == "local" else "tqkq"
    expected_broker = "simulated" if mode == "local" else "tqkq"
    expected_spec_source = "static" if mode == "local" else "tqkq"
    _reject_conflict(
        field="adapters.market_data.mode",
        expected=expected_md,
        actual=md_mode,
        explicit=md_mode_explicit,
        runtime_mode=mode,
    )
    _reject_conflict(
        field="adapters.broker.mode",
        expected=expected_broker,
        actual=broker_mode,
        explicit=broker_mode_explicit,
        runtime_mode=mode,
    )
    _reject_conflict(
        field="instruments.spec_source",
        expected=expected_spec_source,
        actual=instruments.spec_source,
        explicit=spec_source_explicit,
        runtime_mode=mode,
    )
    md_mode = expected_md
    broker_mode = expected_broker
    instruments = _replace_instruments_spec_source(instruments, expected_spec_source)

    if mode == "local":
        if prices_path is None:
            prices_path = str((base_dir / "prices.json").resolve())
    else:
        warmup = runtime.warmup_seconds if runtime.warmup_seconds is not None else 8.0
        params_warmup = md_params.get("warmup_seconds")
        if params_warmup is not None and float(params_warmup) != float(warmup):
            raise ValueError(
                "runtime.mode conflict: field=adapters.market_data.params."
                f"warmup_seconds expected={warmup!r} actual={params_warmup!r}"
            )
        md_params["warmup_seconds"] = warmup
        runtime = _replace_runtime_warmup(runtime, warmup)
        if md_params.get("tq_symbols") is None:
            md_params["tq_symbols"] = (
                main_quotes_for(universe_symbols)
                if instruments.roll_policy.resolve_from_market_data
                else dict(instruments.roll_policy.contracts)
            )
        desired_submit_mode = "dryrun" if mode == "dryrun" else "live"
        submit_mode = broker_params.get("submit_mode")
        if submit_mode is not None and submit_mode != desired_submit_mode:
            raise ValueError(
                f"runtime.mode={mode} conflict: field=adapters.broker.params.submit_mode "
                f"expected={desired_submit_mode!r} actual={submit_mode!r}"
            )
        broker_params["submit_mode"] = desired_submit_mode
        _validate_broker_params(
            broker_mode="tqkq",
            params=broker_params,
            runtime_id=runtime.runtime_id,
        )

    if md_mode == "local_file" and not prices_path:
        raise ValueError("adapters.market_data.prices_path required for local_file")

    adapters = AdaptersSpec(
        market_data=MarketDataSpec(
            mode=cast(Literal["local_file", "tqkq"], md_mode),
            prices_path=prices_path,
            params=md_params,
        ),
        broker=BrokerSpec(
            mode=cast(Literal["simulated", "tqkq"], broker_mode),
            params=broker_params,
        ),
    )

    if adapters.broker.mode == "tqkq":
        _validate_tqkq_contracts(mode=adapters.broker.mode, instruments=instruments)

    return runtime, adapters, instruments


def _reject_conflict(
    *,
    field: str,
    expected: str,
    actual: str,
    explicit: bool,
    runtime_mode: str,
) -> None:
    if explicit and actual != expected:
        raise ValueError(
            f"runtime.mode={runtime_mode} conflict: field={field} "
            f"expected={expected!r} actual={actual!r}"
        )


def _replace_runtime_warmup(runtime: RuntimeSpec, warmup_seconds: float) -> RuntimeSpec:
    return RuntimeSpec(**{**runtime.__dict__, "warmup_seconds": warmup_seconds})


def _replace_instruments_spec_source(
    instruments: InstrumentsSpec,
    spec_source: str,
) -> InstrumentsSpec:
    return InstrumentsSpec(
        trading_sessions=instruments.trading_sessions,
        roll_policy=instruments.roll_policy,
        spec_source=cast(Literal["static", "tqkq"], spec_source),
        specs=instruments.specs,
    )


def _validate_tqkq_contracts(*, mode: str, instruments: InstrumentsSpec) -> None:
    if instruments.roll_policy.mode != "fixed_contract":
        raise ValueError(f"adapters.broker.mode={mode} requires fixed_contract roll_policy")
    if instruments.roll_policy.resolve_from_market_data:
        return
    invalid_contracts = {
        sym: contract
        for sym, contract in instruments.roll_policy.contracts.items()
        if contract.startswith("KQ.") or contract.endswith("_main") or "." not in contract
    }
    if invalid_contracts:
        raise ValueError(
            f"adapters.broker.mode={mode} requires real contracts: "
            f"{invalid_contracts}"
        )


def _validate_broker_params(
    *,
    broker_mode: str,
    params: dict[str, Any],
    runtime_id: str,
) -> None:
    if broker_mode == "tqkq":
        allowed = {"submit_mode", "confirm_live", "confirm_live_token"}
        submit_mode = params.get("submit_mode", "dryrun")
        if submit_mode not in {"dryrun", "live"}:
            raise ValueError("adapters.broker.params.submit_mode must be dryrun or live")
        if submit_mode == "live":
            confirm_live = params.get("confirm_live")
            token_raw = params.get("confirm_live_token")
            token = token_raw if isinstance(token_raw, str) else ""
            if confirm_live is not True or token != runtime_id:
                raise ValueError(
                    "live submit hard gate failed: "
                    "confirm_live must be true and confirm_live_token must match runtime_id; "
                    f"submit_mode={submit_mode!r}, "
                    f"confirm_live={confirm_live is True}, "
                    f"token_present={bool(token)}, "
                    f"expected_token=runtime_id:{runtime_id}, "
                    f"actual_token={_masked_token(token)}"
                )
    else:
        allowed = {
            "order_id_prefix",
            "fill_delay_ticks",
            "partial_fill_ratio",
            "max_partial_steps",
            "max_ticks_to_fill",
            "no_fill",
        }
    extra = set(params) - allowed
    if extra:
        raise ValueError(f"unknown keys at adapters.broker.params: {sorted(extra)}")


def _masked_token(token: str) -> str:
    if not token:
        return "<empty>"
    if len(token) <= 4:
        return f"<len:{len(token)}>"
    return f"{token[:2]}***{token[-2:]}<len:{len(token)}>"
