from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from config.defaults import default_plan
from config.models import (
    AdaptersSpec,
    DataStoreSpec,
    MarketDataSpec,
    PromotionSpec,
    RouterSpec,
    RunPlan,
    RuntimeSpec,
    StrategySpec,
    UniverseSpec,
)


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
        },
        where="root",
    )

    if raw.get("schema_version") != 1:
        raise ValueError("unsupported schema_version")

    env = raw.get("env", base.env)

    # universe
    universe_raw = raw.get("universe", {})
    if not isinstance(universe_raw, dict):
        raise ValueError("universe must be an object")
    _assert_keys(universe_raw, {"symbols"}, where="universe")
    symbols = universe_raw.get("symbols", asdict(base.universe)["symbols"])
    if not isinstance(symbols, list) or not all(isinstance(s, str) for s in symbols):
        raise ValueError("universe.symbols must be list[str]")
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
        {"ticks_live", "ticks_sandbox", "default_quantity", "stop_loss", "take_profit"},
        where="runtime",
    )
    ticks_live = int(runtime_raw.get("ticks_live", base.runtime.ticks_live))
    ticks_sandbox = int(runtime_raw.get("ticks_sandbox", base.runtime.ticks_sandbox))
    default_quantity = float(runtime_raw.get("default_quantity", base.runtime.default_quantity))
    stop_loss = runtime_raw.get("stop_loss", base.runtime.stop_loss)
    take_profit = runtime_raw.get("take_profit", base.runtime.take_profit)
    runtime = RuntimeSpec(
        runtime_id=runtime_id,
        ticks_live=ticks_live,
        ticks_sandbox=ticks_sandbox,
        default_quantity=default_quantity,
        stop_loss=stop_loss if stop_loss is None else float(stop_loss),
        take_profit=take_profit if take_profit is None else float(take_profit),
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
        return Path(v)

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


    # adapters
    adapters_raw = raw.get("adapters", {})
    if not isinstance(adapters_raw, dict):
        raise ValueError("adapters must be an object")
    _assert_keys(adapters_raw, {"market_data"}, where="adapters")

    md_raw = adapters_raw.get("market_data", {})
    if not isinstance(md_raw, dict):
        raise ValueError("adapters.market_data must be an object")
    _assert_keys(md_raw, {"mode", "prices_path"}, where="adapters.market_data")

    md_mode = str(md_raw.get("mode", base.adapters.market_data.mode))
    prices_path = md_raw.get("prices_path", None)
    if prices_path is not None and not isinstance(prices_path, str):
        raise ValueError("adapters.market_data.prices_path must be str")
    if md_mode not in {"simulated", "live_file"}:
        raise ValueError(f"invalid adapters.market_data.mode: {md_mode}")
    if md_mode == "live_file" and not prices_path:
        raise ValueError("adapters.market_data.prices_path required for live_file")

    adapters = AdaptersSpec(
        market_data=MarketDataSpec(
            mode=md_mode,
            prices_path=prices_path,
        )
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
    )
