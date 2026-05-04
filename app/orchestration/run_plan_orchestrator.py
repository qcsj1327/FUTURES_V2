from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

from adapters.storage.datastore_fs import JSONLFileDataStore
from app.orchestration.run_cleanup import clean_runtime_paths
from app.orchestration.session_builder import (
    build_broker_with_specs,
    build_instrument_services,
    build_instrument_specs_registry,
    build_market_data,
    build_strategy_set,
    make_universe_runtime,
)
from app.orchestration.strategy_switch import (
    apply_approved_strategy_switch,
    write_strategy_switch_proposal,
)
from app.orchestration.strategy_switch import (
    approved_path as strategy_switch_approved_path_for,
)
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from config.models import RunPlan
from core.instruments.spec_snapshot import write_specs_snapshot
from optimize.promoter.approved_config import write_approved_config
from optimize.promoter.decision_artifact import write_promotion_decision
from optimize.promoter.manifest_artifact import write_promotion_manifest
from optimize.promoter.promote_from_datastore import promote_from_datastore
from optimize.promoter.promotion_gate import PromotionThresholds
from optimize.promoter.summary_artifact import write_summary_artifact
from research.datastore_replay import summarize_execution_events


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


def orchestrate(
    *,
    resolved: ResolvedPlan,
    clean: bool,
    candidate_id_override: str | None = None,
) -> OrchestrateResult:
    plan = apply_approved_strategy_switch(resolved.plan)
    rid = resolved.runtime_id

    store_root = plan.datastore.store_root
    artifacts_root = plan.datastore.artifacts_root
    live_root = store_root / "live"
    sandbox_root = store_root / "sandbox"

    if clean:
        clean_runtime_paths(runtime_id=rid, store_root=store_root, artifacts_root=artifacts_root)

    plan.datastore.approved_dir.mkdir(parents=True, exist_ok=True)
    plan.datastore.decisions_dir.mkdir(parents=True, exist_ok=True)
    plan.datastore.summaries_dir.mkdir(parents=True, exist_ok=True)
    plan.datastore.manifests_dir.mkdir(parents=True, exist_ok=True)

    strategy_set, priorities, weights = build_strategy_set(plan)

    # ---- live ----
    md_live = build_market_data(plan)
    instrument_specs = build_instrument_specs_registry(plan=plan, market_data=md_live)
    write_specs_snapshot(
        runtime_id=rid,
        specs=instrument_specs.specs_for(list(plan.universe.symbols)),
        output_dir=artifacts_root / "specs",
    )
    broker_live = build_broker_with_specs(plan, md_live, instrument_specs=instrument_specs)
    cfg = RuntimeConfig()
    live_store = JSONLFileDataStore(root_dir=live_root, env="live", runtime_id=rid)
    live_calendar, live_resolver = build_instrument_services(
        plan=plan,
        runtime_id=rid,
        env="live",
        datastore=live_store,
    )

    live_executor = RuntimeFactory.build_live_runtime(
        config=cfg,
        runtime_id=rid,
        market_data=md_live,
        broker=broker_live,
        datastore=live_store,
        trading_calendar=live_calendar,
        instrument_resolver=live_resolver,
    )
    live_executor.max_pending_ticks = plan.execution.max_pending_ticks

    uni_live = make_universe_runtime(
        executor=live_executor,
        market_data=md_live,
        plan=plan,
        strategy_set=strategy_set,
        priorities=priorities,
        weights=weights,
    )
    for _ in range(plan.runtime.ticks_live):
        uni_live.run_tick()

    strategy_switch_proposal_path = write_strategy_switch_proposal(
        runtime_id=rid,
        env="live",
        store=live_store,
        artifacts_root=artifacts_root,
        universe_symbols=list(plan.universe.symbols),
        active_top_n=plan.runtime.active_top_n,
    )
    strategy_switch_approved_candidate = strategy_switch_approved_path_for(
        runtime_id=rid,
        artifacts_root=artifacts_root,
    )
    strategy_switch_approved_artifact_path: Path | None = (
        strategy_switch_approved_candidate
        if strategy_switch_approved_candidate.exists()
        else None
    )

    # ---- sandbox ----
    md_sandbox = build_market_data(plan)
    broker_sandbox = build_broker_with_specs(plan, md_sandbox, instrument_specs=instrument_specs)
    sandbox_store = JSONLFileDataStore(root_dir=sandbox_root, env="sandbox", runtime_id=rid)
    sandbox_calendar, sandbox_resolver = build_instrument_services(
        plan=plan,
        runtime_id=rid,
        env="sandbox",
        datastore=sandbox_store,
    )

    sandbox_executor = RuntimeFactory.build_sandbox_runtime_from_live(
        live_executor,
        runtime_id=rid,
        market_data=md_sandbox,
        broker=broker_sandbox,
        datastore=sandbox_store,
        trading_calendar=sandbox_calendar,
        instrument_resolver=sandbox_resolver,
    )
    sandbox_executor.max_pending_ticks = plan.execution.max_pending_ticks

    uni_sandbox = make_universe_runtime(
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
            strategy_switch_proposal_path=strategy_switch_proposal_path,
            strategy_switch_approved_path=strategy_switch_approved_artifact_path,
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
