from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

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
from optimize.promoter.approved_config import write_approved_config
from optimize.promoter.decision_artifact import write_promotion_decision
from optimize.promoter.manifest_artifact import write_promotion_manifest
from optimize.promoter.promote_from_datastore import promote_from_datastore
from optimize.promoter.promotion_gate import PromotionThresholds
from optimize.promoter.summary_artifact import write_summary_artifact
from research.datastore_replay import summarize_execution_events
from strategies.registry import create_strategy
from strategies.strategy_set import StrategyEntry, StrategySet


@dataclass(frozen=True)
class ResolvedPlan:
    runtime_id: str
    env: str
    plan: RunPlan
    plan_meta: dict[str, Any] | None


@dataclass(frozen=True)
class OrchestrateResult:
    runtime_id: str
    live_store_dir: str
    sandbox_store_dir: str
    summaries: dict[str, str]
    decision_path: str | None
    approved_path: str | None
    manifest_path: str | None


def resolve_plan(*, plan: RunPlan, plan_meta: dict[str, Any] | None) -> ResolvedPlan:
    return ResolvedPlan(
        runtime_id=plan.runtime.runtime_id,
        env=plan.env,
        plan=plan,
        plan_meta=plan_meta,
    )


def compute_plan_meta_from_file(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "path": str(path),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "config": json.loads(raw.decode("utf-8")),
    }


def _rm_tree(p: Path) -> None:
    if p.exists():
        shutil.rmtree(p)


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

        universe = list(plan.universe.symbols)
        for s in list(universe):
            if not s.endswith("_main"):
                universe.append(f"{s}_main")

        return SimulatedMarketDataV2(
            symbols=universe,
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

    strategy_set = StrategySet(entries)
    priorities = {e.name: e.priority for e in entries}
    weights = {s.name: float(s.weight) for s in plan.strategies}
    return strategy_set, priorities, weights


def _make_universe_runtime(
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
    )


def orchestrate(
    *,
    resolved: ResolvedPlan,
    clean: bool,
    candidate_id_override: str | None = None,
) -> OrchestrateResult:
    plan = resolved.plan
    rid = resolved.runtime_id

    store_root = plan.datastore.store_root
    artifacts_root = plan.datastore.artifacts_root
    live_root = store_root / "live"
    sandbox_root = store_root / "sandbox"

    if clean:
        _rm_tree(store_root)
        _rm_tree(artifacts_root)

    plan.datastore.approved_dir.mkdir(parents=True, exist_ok=True)
    plan.datastore.decisions_dir.mkdir(parents=True, exist_ok=True)
    plan.datastore.summaries_dir.mkdir(parents=True, exist_ok=True)
    plan.datastore.manifests_dir.mkdir(parents=True, exist_ok=True)

    strategy_set, priorities, weights = _build_strategy_set(plan)

    # ---- live ----
    md_live = _build_market_data(plan)
    broker_live = SimulatedBroker(md_live)
    cfg = RuntimeConfig()
    live_store = JSONLFileDataStore(root_dir=live_root, env="live", runtime_id=rid)

    live_executor = RuntimeFactory.build_live_runtime(
        config=cfg,
        runtime_id=rid,
        market_data=md_live,
        broker=broker_live,
        datastore=live_store,
    )

    uni_live = _make_universe_runtime(
        executor=live_executor,
        market_data=md_live,
        plan=plan,
        strategy_set=strategy_set,
        priorities=priorities,
        weights=weights,
    )
    for _ in range(plan.runtime.ticks_live):
        uni_live.run_tick()

    # ---- sandbox ----
    md_sandbox = _build_market_data(plan)
    broker_sandbox = SimulatedBroker(md_sandbox)
    sandbox_store = JSONLFileDataStore(root_dir=sandbox_root, env="sandbox", runtime_id=rid)

    sandbox_executor = RuntimeFactory.build_sandbox_runtime_from_live(
        live_executor,
        runtime_id=rid,
        market_data=md_sandbox,
        broker=broker_sandbox,
        datastore=sandbox_store,
    )

    uni_sandbox = _make_universe_runtime(
        executor=sandbox_executor,
        market_data=md_sandbox,
        plan=plan,
        strategy_set=strategy_set,
        priorities=priorities,
        weights=weights,
    )
    for _ in range(plan.runtime.ticks_sandbox):
        uni_sandbox.run_tick()

    # ---- promotion ----
    thresholds = PromotionThresholds(
        min_events=plan.promotion.min_events,
        min_success_rate_improvement=plan.promotion.min_success_rate_improvement,
        max_consecutive_failures=plan.promotion.max_consecutive_failures,
    )

    decision = promote_from_datastore(
        current_store=live_store,
        current_env="live",
        candidate_store=sandbox_store,
        candidate_env="sandbox",
        thresholds=thresholds,
    )

    decision_payload = {
        "approved": decision.approved,
        "reasons": list(decision.reasons),
        "deltas": dict(decision.deltas),
    }

    cur_events = live_store.read_fill_events(env="live")
    cand_events = sandbox_store.read_fill_events(env="sandbox")
    cur_metrics = asdict(summarize_execution_events(cur_events))
    cand_metrics = asdict(summarize_execution_events(cand_events))

    current_summary_path: Path | None = None
    candidate_summary_path: Path | None = None
    decision_path: Path | None = None
    approved_path: Path | None = None
    manifest_path: Path | None = None

    summaries: dict[str, str] = {}

    if plan.promotion.write_summary:
        current_summary_path = write_summary_artifact(
            runtime_id=rid,
            role="current",
            summary=cur_metrics,
            output_dir=plan.datastore.summaries_dir,
        )
        candidate_summary_path = write_summary_artifact(
            runtime_id=rid,
            role="candidate",
            summary=cand_metrics,
            output_dir=plan.datastore.summaries_dir,
        )
        summaries["current"] = str(current_summary_path)
        summaries["candidate"] = str(candidate_summary_path)

    if plan.promotion.write_decision:
        decision_path = write_promotion_decision(
            runtime_id=rid,
            decision=decision_payload,
            thresholds=asdict(thresholds),
            current_metrics=cur_metrics,
            candidate_metrics=cand_metrics,
            output_dir=plan.datastore.decisions_dir,
        )

    candidate_id = candidate_id_override or f"cand_{rid}"

    if plan.promotion.write_approved:
        approved_path = write_approved_config(
            approved=bool(decision_payload["approved"]),
            candidate_id=candidate_id,
            candidate_config={
                "universe": {"symbols": list(plan.universe.symbols)},
                "strategies": [asdict(s) for s in plan.strategies],
            },
            decision_deltas=dict(decision.deltas),
            thresholds=asdict(thresholds),
            current_metrics=cur_metrics,
            candidate_metrics=cand_metrics,
            output_dir=plan.datastore.approved_dir,
            filename=f"approved_{candidate_id}.json",
        )

    if plan.promotion.write_manifest:
        plan_payload: Mapping[str, Any] | None = None
        plan_path_str: str | None = None
        plan_sha256: str | None = None
        if resolved.plan_meta and isinstance(resolved.plan_meta.get("config"), dict):
            plan_payload = cast(Mapping[str, Any], resolved.plan_meta["config"])
            plan_path_str = cast(str | None, resolved.plan_meta.get("path"))
            plan_sha256 = cast(str | None, resolved.plan_meta.get("sha256"))

        manifest_path = write_promotion_manifest(
            runtime_id=rid,
            candidate_id=candidate_id,
            candidate_config={
                "universe": {"symbols": list(plan.universe.symbols)},
                "strategies": [asdict(s) for s in plan.strategies],
            },
            thresholds=asdict(thresholds),
            current_summary_path=current_summary_path,
            candidate_summary_path=candidate_summary_path,
            decision_path=decision_path,
            approved_path=approved_path,
            plan=plan_payload,
            plan_path=plan_path_str,
            plan_sha256=plan_sha256,
            output_dir=plan.datastore.manifests_dir,
        )

    return OrchestrateResult(
        runtime_id=rid,
        live_store_dir=str(live_root / rid),
        sandbox_store_dir=str(sandbox_root / rid),
        summaries=summaries,
        decision_path=str(decision_path) if decision_path is not None else None,
        approved_path=str(approved_path) if approved_path is not None else None,
        manifest_path=str(manifest_path) if manifest_path is not None else None,
    )
