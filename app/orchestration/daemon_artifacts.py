from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from adapters.storage.datastore_fs import JSONLFileDataStore
from app.orchestration.strategy_switch import (
    write_strategy_switch_auto_approved,
    write_strategy_switch_proposal,
)
from config.instrument_universe import default_symbols
from core.services.runtime.execution_summary import summarize_execution_events
from optimize.promoter.manifest_artifact import write_promotion_manifest
from optimize.promoter.promotion_gate import PromotionThresholds
from optimize.promoter.summary_artifact import write_summary_artifact


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
    scope: str,
    store_root: Path,
    artifacts_root: Path,
    candidate_id: str,
    thresholds: PromotionThresholds,
    plan_meta: dict[str, Any] | None,
    write_manifest: bool,
    write_summary: bool,
    status: str = "running",
    include_strategy_switch: bool = True,
) -> dict[str, Path | None]:
    dirs = _artifact_dirs(artifacts_root)
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)

    store = JSONLFileDataStore(root_dir=store_root / scope, scope=scope, runtime_id=runtime_id)
    metrics = asdict(summarize_execution_events(store.read_fill_events(scope=scope)))
    plan_cfg = _plan_config(plan_meta)
    universe_symbols = _universe_symbols(plan_cfg)
    active_top_n = _active_top_n(plan_cfg)
    switch_cfg = plan_cfg.get("strategy_switch")
    switch_cfg = switch_cfg if isinstance(switch_cfg, Mapping) else {}

    current_path: Path | None = None
    if write_summary or write_manifest:
        current_path = write_summary_artifact(
            runtime_id=runtime_id,
            role="current",
            summary=metrics,
            output_dir=dirs["summaries"],
            filename=f"current_{runtime_id}.json",
            status=status,
        )
    strategy_switch_proposal_path: Path | None = None
    strategy_switch_approved_path: Path | None = None
    if include_strategy_switch:
        strategy_switch_proposal_path = write_strategy_switch_proposal(
            runtime_id=runtime_id,
            scope=scope,
            store=store,
            artifacts_root=artifacts_root,
            universe_symbols=universe_symbols,
            active_top_n=active_top_n,
            current_enabled_by_symbol=_enabled_by_symbol(switch_cfg),
            approval_required=bool(switch_cfg.get("approval_required", False)),
            min_score=float(switch_cfg.get("min_score", 1.0)),
            max_enabled_strategies_per_symbol=int(
                switch_cfg.get("max_enabled_strategies_per_symbol", 1)
            ),
        )
        strategy_switch_approved_path = write_strategy_switch_auto_approved(
            proposal_path=strategy_switch_proposal_path,
        )

    manifest_path: Path | None = None
    if write_manifest:
        plan_path: str | None = None
        plan_sha256: str | None = None

        if plan_meta and isinstance(plan_meta.get("effective_config_summary"), dict):
            plan_path = cast(str | None, plan_meta.get("path"))
            plan_sha256 = cast(str | None, plan_meta.get("sha256"))

        manifest_path = write_promotion_manifest(
            runtime_id=runtime_id,
            candidate_id=candidate_id,
            candidate_config={"runtime_profile": scope, "datastore_scope": scope},
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
            runtime_profile=scope,
            datastore_scope=scope,
            status=status,
        )

    return {
        "current_summary_path": current_path,
        "candidate_summary_path": None,
        "strategy_switch_proposal_path": strategy_switch_proposal_path,
        "manifest_path": manifest_path,
    }


def _plan_config(plan_meta: dict[str, Any] | None) -> Mapping[str, Any]:
    if plan_meta and isinstance(plan_meta.get("effective_config_summary"), dict):
        return cast(Mapping[str, Any], plan_meta["effective_config_summary"])
    return {}


def _universe_symbols(plan_cfg: Mapping[str, Any]) -> list[str]:
    universe = plan_cfg.get("universe")
    if isinstance(universe, dict):
        symbols = universe.get("symbols")
        if isinstance(symbols, list):
            return [x for x in symbols if isinstance(x, str)]
    return default_symbols()


def _active_top_n(plan_cfg: Mapping[str, Any]) -> int:
    runtime = plan_cfg.get("runtime")
    if isinstance(runtime, dict):
        value = runtime.get("active_top_n", 0)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def _enabled_by_symbol(switch_cfg: Mapping[str, Any]) -> dict[str, list[str]]:
    raw = switch_cfg.get("enabled_by_symbol")
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, list[str]] = {}
    for sym, names in raw.items():
        if isinstance(sym, str) and isinstance(names, list):
            parsed = sorted({name for name in names if isinstance(name, str) and name})
            if parsed:
                out[sym] = parsed
    return out
