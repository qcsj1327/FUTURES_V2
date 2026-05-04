from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from adapters.storage.datastore_fs import JSONLFileDataStore
from app.orchestration.strategy_switch import (
    approved_path as strategy_switch_approved_path_for,
)
from app.orchestration.strategy_switch import write_strategy_switch_proposal
from optimize.promoter.manifest_artifact import write_promotion_manifest
from optimize.promoter.promotion_gate import PromotionThresholds
from optimize.promoter.summary_artifact import write_summary_artifact
from research.datastore_replay import summarize_execution_events


def _now_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _artifact_dirs(artifacts_root: Path) -> dict[str, Path]:
    return {
        "summaries": artifacts_root / "summaries",
        "manifests": artifacts_root / "manifests",
    }


def write_daemon_artifacts(
    *,
    runtime_id: str,
    env: str,
    store_root: Path,
    artifacts_root: Path,
    candidate_id: str,
    thresholds: PromotionThresholds,
    plan_meta: dict[str, Any] | None,
    write_manifest: bool,
    write_summary: bool,
) -> dict[str, Path | None]:
    dirs = _artifact_dirs(artifacts_root)
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    store = JSONLFileDataStore(root_dir=store_root / env, env=env, runtime_id=runtime_id)
    metrics = asdict(summarize_execution_events(store.read_fill_events(env=env)))
    plan_cfg = _plan_config(plan_meta)
    universe_symbols = _universe_symbols(plan_cfg)
    active_top_n = _active_top_n(plan_cfg)

    current_path: Path | None = None
    if write_summary or write_manifest:
        current_path = write_summary_artifact(
            runtime_id=runtime_id,
            role="current",
            summary=metrics,
            output_dir=dirs["summaries"],
            filename=f"current_{runtime_id}.json",
        )
    strategy_switch_proposal_path = write_strategy_switch_proposal(
        runtime_id=runtime_id,
        env=env,
        store=store,
        artifacts_root=artifacts_root,
        universe_symbols=universe_symbols,
        active_top_n=active_top_n,
    )
    strategy_switch_approved_candidate = strategy_switch_approved_path_for(
        runtime_id=runtime_id,
        artifacts_root=artifacts_root,
    )
    strategy_switch_approved_path: Path | None = (
        strategy_switch_approved_candidate
        if strategy_switch_approved_candidate.exists()
        else None
    )

    manifest_path: Path | None = None
    if write_manifest:
        plan_path: str | None = None
        plan_sha256: str | None = None

        if plan_meta and isinstance(plan_meta.get("config"), dict):
            plan_path = cast(str | None, plan_meta.get("path"))
            plan_sha256 = cast(str | None, plan_meta.get("sha256"))

        manifest_path = write_promotion_manifest(
            runtime_id=runtime_id,
            candidate_id=candidate_id,
            candidate_config={"env": env},
            thresholds=asdict(thresholds),
            current_summary_path=current_path,
            candidate_summary_path=None,
            decision_path=None,
            approved_path=None,
            strategy_switch_proposal_path=strategy_switch_proposal_path,
            strategy_switch_approved_path=strategy_switch_approved_path,
            plan=plan_cfg,
            plan_path=plan_path,
            plan_sha256=plan_sha256,
            output_dir=dirs["manifests"],
            filename=f"manifest_{runtime_id}_{_now_tag()}.json",
            run_mode="daemon",
            env=env,
        )

    return {
        "current_summary_path": current_path,
        "candidate_summary_path": None,
        "strategy_switch_proposal_path": strategy_switch_proposal_path,
        "manifest_path": manifest_path,
    }


def _plan_config(plan_meta: dict[str, Any] | None) -> Mapping[str, Any]:
    if plan_meta and isinstance(plan_meta.get("config"), dict):
        return cast(Mapping[str, Any], plan_meta["config"])
    return {}


def _universe_symbols(plan_cfg: Mapping[str, Any]) -> list[str]:
    universe = plan_cfg.get("universe")
    if isinstance(universe, dict):
        symbols = universe.get("symbols")
        if isinstance(symbols, list):
            return [x for x in symbols if isinstance(x, str)]
    return []


def _active_top_n(plan_cfg: Mapping[str, Any]) -> int:
    runtime = plan_cfg.get("runtime")
    if isinstance(runtime, dict):
        value = runtime.get("active_top_n", 0)
        if isinstance(value, (int, float)):
            return int(value)
    return 0
