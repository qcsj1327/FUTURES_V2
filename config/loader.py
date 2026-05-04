from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal, cast

from config.defaults import default_plan
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
    TradingSessionSpec,
    UniverseSpec,
)

RuntimeMode = Literal["simulated_v2", "live_file", "tqkq_sim", "tqkq_live"]


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
        ss = sraw.get("symbols", [])
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
            "ticks_sandbox",
            "default_quantity",
            "stop_loss",
            "take_profit",
            "active_top_n",
            "rank_window",
            "rank_metric",
            "rank_refresh_every",
            "rank_emit_events",
        },
        where="runtime",
    )
    runtime_mode_explicit = "mode" in runtime_raw
    runtime_mode_raw = str(runtime_raw.get("mode", base.runtime.mode))
    if runtime_mode_raw not in {"simulated_v2", "live_file", "tqkq_sim", "tqkq_live"}:
        raise ValueError(f"invalid runtime.mode: {runtime_mode_raw}")
    runtime_mode = cast(RuntimeMode, runtime_mode_raw)
    warmup_raw = runtime_raw.get("warmup_seconds", base.runtime.warmup_seconds)
    warmup_seconds = None if warmup_raw is None else float(warmup_raw)
    ticks_live = int(runtime_raw.get("ticks_live", base.runtime.ticks_live))
    ticks_sandbox = int(runtime_raw.get("ticks_sandbox", base.runtime.ticks_sandbox))
    default_quantity = float(runtime_raw.get("default_quantity", base.runtime.default_quantity))
    stop_loss = runtime_raw.get("stop_loss", base.runtime.stop_loss)
    take_profit = runtime_raw.get("take_profit", base.runtime.take_profit)
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
    runtime = RuntimeSpec(
        runtime_id=runtime_id,
        ticks_live=ticks_live,
        ticks_sandbox=ticks_sandbox,
        default_quantity=default_quantity,
        mode=runtime_mode,
        warmup_seconds=warmup_seconds,
        stop_loss=stop_loss if stop_loss is None else float(stop_loss),
        take_profit=take_profit if take_profit is None else float(take_profit),
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
    _assert_keys(roll_raw, {"mode", "contracts"}, where="instruments.roll_policy")
    roll_mode = str(roll_raw.get("mode", base.instruments.roll_policy.mode))
    if roll_mode not in {"fixed_contract", "fixed_main"}:
        raise ValueError(f"invalid instruments.roll_policy.mode: {roll_mode}")
    contracts_raw = roll_raw.get("contracts", base.instruments.roll_policy.contracts)
    if not isinstance(contracts_raw, dict):
        raise ValueError("instruments.roll_policy.contracts must be object")
    contracts: dict[str, str] = {}
    for sym, contract in contracts_raw.items():
        if not isinstance(sym, str) or sym.endswith("_main"):
            raise ValueError("instruments.roll_policy.contracts keys must be base symbols")
        if not isinstance(contract, str) or not contract:
            raise ValueError(f"instruments.roll_policy.contracts.{sym} must be non-empty str")
        contracts[sym] = contract
    for sym in universe.symbols:
        if sym not in contracts:
            raise ValueError(f"missing instruments.roll_policy.contracts.{sym}")

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
        roll_policy=RollPolicySpec(mode=roll_mode, contracts=contracts),
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
    if md_mode not in {"tqkq", "simulated", "simulated_v2", "live_file"}:
        raise ValueError(f"invalid adapters.market_data.mode: {md_mode}")
    if md_mode == "live_file" and not prices_path:
        raise ValueError("adapters.market_data.prices_path required for live_file")

    adapters = AdaptersSpec(
        market_data=MarketDataSpec(
            mode=md_mode,
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
    if broker_mode not in {"simulated", "tqkq_sim", "tqkq_live"}:
        raise ValueError(f"invalid adapters.broker.mode: {broker_mode}")
    broker_params = broker_raw.get("params", {})
    if not isinstance(broker_params, dict):
        raise ValueError("adapters.broker.params must be object")
    _validate_broker_params(broker_mode=broker_mode, params=broker_params)
    runtime, adapters, instruments = _normalize_runtime_mode(
        runtime=runtime,
        runtime_mode_explicit=runtime_mode_explicit,
        md_mode=md_mode,
        md_mode_explicit=md_mode_explicit,
        prices_path=prices_path,
        md_params=dict(md_params),
        broker_mode=broker_mode,
        broker_mode_explicit=broker_mode_explicit,
        broker_params=dict(broker_params),
        instruments=instruments,
        spec_source_explicit="spec_source" in instruments_raw,
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
        execution=execution,
        risk=risk,
        instruments=instruments,
    )


def _normalize_runtime_mode(
    *,
    runtime: RuntimeSpec,
    runtime_mode_explicit: bool,
    md_mode: str,
    md_mode_explicit: bool,
    prices_path: str | None,
    md_params: dict[str, Any],
    broker_mode: str,
    broker_mode_explicit: bool,
    broker_params: dict[str, Any],
    instruments: InstrumentsSpec,
    spec_source_explicit: bool,
    base_dir: Path,
) -> tuple[RuntimeSpec, AdaptersSpec, InstrumentsSpec]:
    if runtime_mode_explicit:
        mode = runtime.mode
        expected_md = {
            "simulated_v2": "simulated_v2",
            "live_file": "live_file",
            "tqkq_sim": "tqkq",
            "tqkq_live": "tqkq",
        }[mode]
        expected_broker = (
            "tqkq_live"
            if mode == "tqkq_live"
            else "tqkq_sim"
            if mode == "tqkq_sim"
            else "simulated"
        )
        expected_spec_source = "tqkq" if mode in {"tqkq_sim", "tqkq_live"} else "static"
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
        if mode == "live_file" and prices_path is None:
            prices_path = str((base_dir / "prices.json").resolve())
        if mode in {"tqkq_sim", "tqkq_live"}:
            warmup = runtime.warmup_seconds if runtime.warmup_seconds is not None else 8.0
            params_warmup = md_params.get("warmup_seconds")
            if params_warmup is not None and float(params_warmup) != float(warmup):
                raise ValueError(
                    "runtime.mode=tqkq_sim conflict: field=adapters.market_data.params."
                    f"warmup_seconds expected={warmup!r} actual={params_warmup!r}"
                )
            md_params["warmup_seconds"] = warmup
            runtime = _replace_runtime_warmup(runtime, warmup)
            tq_symbols = md_params.get("tq_symbols")
            if tq_symbols is None:
                md_params["tq_symbols"] = dict(instruments.roll_policy.contracts)

    else:
        if broker_mode == "tqkq_sim" and md_mode != "tqkq":
            raise ValueError("tqkq_sim requires adapters.market_data.mode=tqkq")
        runtime = _replace_runtime_mode(runtime, _derive_runtime_mode(md_mode, broker_mode))

    if md_mode == "live_file" and not prices_path:
        raise ValueError("adapters.market_data.prices_path required for live_file")

    adapters = AdaptersSpec(
        market_data=MarketDataSpec(
            mode=md_mode,
            prices_path=prices_path,
            params=md_params,
        ),
        broker=BrokerSpec(
            mode=cast(Literal["simulated", "tqkq_sim", "tqkq_live"], broker_mode),
            params=broker_params,
        ),
    )

    if adapters.broker.mode in {"tqkq_sim", "tqkq_live"}:
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


def _derive_runtime_mode(md_mode: str, broker_mode: str) -> RuntimeMode:
    if broker_mode == "tqkq_live":
        return "tqkq_live"
    if broker_mode == "tqkq_sim":
        return "tqkq_sim"
    if md_mode == "live_file":
        return "live_file"
    return "simulated_v2"


def _replace_runtime_mode(runtime: RuntimeSpec, mode: RuntimeMode) -> RuntimeSpec:
    return RuntimeSpec(**{**runtime.__dict__, "mode": mode})


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
    invalid_contracts = {
        sym: contract
        for sym, contract in instruments.roll_policy.contracts.items()
        if contract.endswith("_main") or "." not in contract
    }
    if invalid_contracts:
        raise ValueError(
            f"adapters.broker.mode={mode} requires real contracts: "
            f"{invalid_contracts}"
        )


def _validate_broker_params(*, broker_mode: str, params: dict[str, Any]) -> None:
    if broker_mode == "tqkq_live":
        allowed = {"dry_run"}
    elif broker_mode == "tqkq_sim":
        allowed = {"no_fill"}
    else:
        allowed = {
            "fill_delay_ticks",
            "partial_fill_ratio",
            "max_partial_steps",
            "max_ticks_to_fill",
            "no_fill",
        }
    extra = set(params) - allowed
    if extra:
        raise ValueError(f"unknown keys at adapters.broker.params: {sorted(extra)}")
