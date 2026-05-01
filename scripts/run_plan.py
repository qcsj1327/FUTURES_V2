from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from app.universe_runtime import UniverseRuntime
from config.loader import load_plan
from config.models import RunPlan, StrategySpec
from core.signal_router.router import RouterConfig
from optimize.promoter.approved_config import write_approved_config
from optimize.promoter.decision_artifact import write_promotion_decision
from optimize.promoter.manifest_artifact import write_promotion_manifest
from optimize.promoter.promote_from_datastore import promote_from_datastore
from optimize.promoter.promotion_gate import PromotionThresholds
from optimize.promoter.summary_artifact import write_summary_artifact
from research.datastore_replay import replay_execution_events, summarize_execution_events
from strategies.base.strategy import Strategy
from strategies.registry import create_strategy
from strategies.strategy_set import StrategyEntry, StrategySet


def _rm_tree(path: Path) -> None:
    if not path.exists():
        return
    for p in sorted(path.rglob("*"), reverse=True):
        if p.is_file() or p.is_symlink():
            p.unlink()
        else:
            p.rmdir()
    path.rmdir()


def _make_runtime_config(*, runtime_id: str, default_quantity: float) -> RuntimeConfig:
    cfg = RuntimeConfig()
    try:
        cfg.runtime_id = runtime_id  # type: ignore[misc]
    except Exception:
        pass
    try:
        cfg.default_quantity = default_quantity  # type: ignore[misc]
    except Exception:
        pass
    return cfg


def _strategy_instance(name: str, params: dict[str, object]) -> Strategy:
    return create_strategy(name=name, params=params)


def _build_strategy_entries(strategies: list[StrategySpec]) -> list[StrategyEntry]:
    entries: list[StrategyEntry] = []
    for s in strategies:
        entries.append(
            StrategyEntry(
                name=s.name,
                strategy=_strategy_instance(s.name, s.params),
                symbols=s.symbols,
                priority=s.priority,
                params=s.params,
            )
        )
    return entries


def run_all(plan: RunPlan, *, clean: bool) -> None:
    store_root = Path(plan.datastore.store_root)
    approved_dir = Path(plan.datastore.approved_dir)
    decisions_dir = Path(plan.datastore.decisions_dir)
    summaries_dir = Path(plan.datastore.summaries_dir)
    manifests_dir = Path(plan.datastore.manifests_dir)

    if clean:
        _rm_tree(store_root)
        _rm_tree(approved_dir)
        _rm_tree(decisions_dir)
        _rm_tree(summaries_dir)
        _rm_tree(manifests_dir)

    cfg = _make_runtime_config(
        runtime_id=plan.runtime.runtime_id,
        default_quantity=plan.runtime.default_quantity,
    )

    md = SimulatedMarketData()
    broker = SimulatedBroker(md)

    entries = _build_strategy_entries(plan.strategies)
    sset = StrategySet(entries)
    priorities = {e.name: e.priority for e in entries}
    weights = {e.name: getattr(e, "weight", 1.0) for e in plan.strategies}
    router_cfg = RouterConfig(mode=plan.router.mode, tie_breaker=plan.router.tie_breaker)

    # -------- Live session --------
    live_executor = RuntimeFactory.build_live_runtime(
        config=cfg,
        runtime_id=plan.runtime.runtime_id,
        market_data=md,
        broker=broker,
    )
    uni_live = UniverseRuntime(
        executor=live_executor,
        market_data=md,
        universe_symbols=plan.universe.symbols,
        strategy_set=sset,
        strategy_priorities=priorities,
        strategy_weights=weights,
        router_config=router_cfg,
    )
    for _ in range(plan.runtime.ticks_live):
        uni_live.run_tick()

    # -------- Sandbox session --------
    sandbox_executor = RuntimeFactory.build_sandbox_runtime_from_live(
        live_executor,
        runtime_id=plan.runtime.runtime_id,
    )
    uni_sandbox = UniverseRuntime(
        executor=sandbox_executor,
        market_data=md,
        universe_symbols=plan.universe.symbols,
        strategy_set=sset,
        strategy_priorities=priorities,
        strategy_weights=weights,
        router_config=router_cfg,
    )
    for _ in range(plan.runtime.ticks_sandbox):
        uni_sandbox.run_tick()

    # datastore must exist (Factory defaults inject FS store)
    live_store = live_executor.datastore
    sandbox_store = sandbox_executor.datastore
    assert live_store is not None
    assert sandbox_store is not None

    # -------- Promotion --------
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

    # summaries for audit
    cur_events = replay_execution_events(live_store, env="live")
    cand_events = replay_execution_events(sandbox_store, env="sandbox")
    cur_summary = summarize_execution_events(cur_events)
    cand_summary = summarize_execution_events(cand_events)
    cur_metrics = asdict(cur_summary)
    cand_metrics = asdict(cand_summary)

    cur_path = None
    cand_path = None
    if plan.promotion.write_summary:
        cur_path = write_summary_artifact(
            runtime_id=plan.runtime.runtime_id,
            role="current",
            summary=cur_metrics,
            output_dir=summaries_dir,
        )
        cand_path = write_summary_artifact(
            runtime_id=plan.runtime.runtime_id,
            role="candidate",
            summary=cand_metrics,
            output_dir=summaries_dir,
        )

    decision_path = None
    if plan.promotion.write_decision:
        decision_path = write_promotion_decision(
            runtime_id=plan.runtime.runtime_id,
            decision=asdict(decision),
            thresholds=asdict(thresholds),
            current_metrics=cur_metrics,
            candidate_metrics=cand_metrics,
            output_dir=decisions_dir,
        )

    candidate_id = f"cand_{plan.runtime.runtime_id}"
    candidate_config = {
        "universe": asdict(plan.universe),
        "strategies": [asdict(s) for s in plan.strategies],
    }

    approved_path = None
    if plan.promotion.write_approved:
        approved_path = write_approved_config(
            approved=decision.approved,
            candidate_id=candidate_id,
            candidate_config=candidate_config,
            decision_deltas=decision.deltas,
            thresholds=asdict(thresholds),
            current_metrics=cur_metrics,
            candidate_metrics=cand_metrics,
            output_dir=approved_dir,
            filename=f"approved_{candidate_id}.json",
        )

    if plan.promotion.write_manifest:
        _ = write_promotion_manifest(
            runtime_id=plan.runtime.runtime_id,
            candidate_id=candidate_id,
            candidate_config=candidate_config,
            thresholds=asdict(thresholds),
            current_summary_path=cur_path,
            candidate_summary_path=cand_path,
            decision_path=decision_path,
            approved_path=approved_path,
            output_dir=manifests_dir,
        )

    print(json.dumps(asdict(decision), ensure_ascii=False, indent=2, default=str))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_plan",
        description="Run a full plan (multi-symbol/multi-strategy) end-to-end.",
    )
    parser.add_argument(
        "--config",
        type=str,
        default="",
        help="Optional plan json (schema_version=1).",
    )
    parser.add_argument("--runtime-id", type=str, default="r_plan")
    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args(argv)

    plan = load_plan(Path(args.config) if args.config else None, runtime_id=args.runtime_id)
    run_all(plan, clean=args.clean)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
