from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, is_dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_fs import JSONLFileDataStore
from app.orchestration.run_plan_orchestrator import orchestrate, resolve_plan
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from config.defaults import default_plan
from optimize.promoter.approved_config import write_approved_config
from optimize.promoter.decision_artifact import write_promotion_decision
from optimize.promoter.manifest_artifact import write_promotion_manifest
from optimize.promoter.promote_from_datastore import promote_from_datastore
from optimize.promoter.promotion_gate import PromotionThresholds
from optimize.promoter.summary_artifact import write_summary_artifact
from research.datastore_replay import replay_execution_events, summarize_execution_events


def _utc_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _rm_tree(path: Path) -> None:
    if not path.exists():
        return
    for p in sorted(path.rglob("*"), reverse=True):
        if p.is_file() or p.is_symlink():
            p.unlink()
        else:
            p.rmdir()
    path.rmdir()


def _make_config(*, runtime_id: str, symbol: str | None) -> RuntimeConfig:
    cfg = RuntimeConfig()

    # runtime_id override (RuntimeConfig may be treated as read-only by type checker)
    try:
        cfg.runtime_id = runtime_id  # type: ignore[misc]
    except Exception:
        if is_dataclass(cfg):
            cfg = replace(cfg, runtime_id=runtime_id)

    if symbol is not None:
        try:
            cfg.symbol = symbol  # type: ignore[misc]
        except Exception:
            if is_dataclass(cfg):
                cfg = replace(cfg, symbol=symbol)

    return cfg


def run_live(*, cfg: RuntimeConfig, ticks: int) -> None:
    md = SimulatedMarketData()
    broker = SimulatedBroker(md)
    rt = RuntimeFactory.build_live_runtime(config=cfg, market_data=md, broker=broker)
    for _ in range(ticks):
        rt.run_market_once()


def run_sandbox(*, live_cfg: RuntimeConfig, ticks: int) -> None:
    md = SimulatedMarketData()
    broker = SimulatedBroker(md)

    live_rt = RuntimeFactory.build_live_runtime(config=live_cfg, market_data=md, broker=broker)
    live_rt.run_market_once()  # ensure a baseline snapshot exists

    sandbox_rt = RuntimeFactory.build_sandbox_runtime_from_live(live_rt)
    for _ in range(ticks):
        sandbox_rt.run_market_once()


def run_promote(
    *,
    cfg: RuntimeConfig,
    thresholds: PromotionThresholds,
    candidate_strategy_name: str,
    candidate_params_json: str,
    store_root: Path,
    approved_dir: Path,
    decision_dir: Path,
    summary_dir: Path,
    manifest_dir: Path,
    write_summary: bool,
    write_decision: bool,
    write_artifact: bool,
    write_manifest: bool,
) -> tuple[Path | None, Path | None, Path | None, Path | None]:
    current_store = JSONLFileDataStore(
        root_dir=store_root / "live",
        env="live",
        runtime_id=cfg.runtime_id,
    )
    candidate_store = JSONLFileDataStore(
        root_dir=store_root / "sandbox",
        env="sandbox",
        runtime_id=cfg.runtime_id,
    )

    cur_events = replay_execution_events(current_store, env="live")
    cand_events = replay_execution_events(candidate_store, env="sandbox")
    cur_summary = summarize_execution_events(cur_events)
    cand_summary = summarize_execution_events(cand_events)
    cur_metrics = asdict(cur_summary)
    cand_metrics = asdict(cand_summary)

    cur_path: Path | None = None
    cand_path: Path | None = None
    if write_summary:
        cur_path = write_summary_artifact(
            runtime_id=cfg.runtime_id,
            role="current",
            summary=cur_metrics,
            output_dir=summary_dir,
        )
        cand_path = write_summary_artifact(
            runtime_id=cfg.runtime_id,
            role="candidate",
            summary=cand_metrics,
            output_dir=summary_dir,
        )

    decision = promote_from_datastore(
        current_store=current_store,
        current_env="live",
        candidate_store=candidate_store,
        candidate_env="sandbox",
        thresholds=thresholds,
    )

    print(
        "PromotionDecision:",
        json.dumps(asdict(decision), ensure_ascii=False, indent=2, default=str),
    )

    decision_path: Path | None = None
    if write_decision:
        decision_path = write_promotion_decision(
            runtime_id=cfg.runtime_id,
            decision=asdict(decision),
            thresholds=asdict(thresholds),
            current_metrics=cur_metrics,
            candidate_metrics=cand_metrics,
            output_dir=decision_dir,
        )

    candidate_id = f"cand_{cfg.runtime_id}_{_utc_tag()}"
    candidate_config: dict[str, Any] = {
        "strategy_name": candidate_strategy_name,
        "params": json.loads(candidate_params_json) if candidate_params_json else {},
    }

    approved_path: Path | None = None
    if write_artifact:
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

    manifest_path: Path | None = None
    if write_manifest:
        manifest_path = write_promotion_manifest(
            runtime_id=cfg.runtime_id,
            candidate_id=candidate_id,
            candidate_config=candidate_config,
            thresholds=asdict(thresholds),
            current_summary_path=cur_path,
            candidate_summary_path=cand_path,
            decision_path=decision_path,
            approved_path=approved_path,
            output_dir=manifest_dir,
        )
        print("Manifest:", str(manifest_path))

    return cur_path, cand_path, decision_path, approved_path
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_local",
        description="Run live/sandbox/promote locally (orchestrator-driven).",
    )
    parser.add_argument(
        "mode",
        type=str,
        nargs="?",
        default="all",
        help="live | sandbox | promote | all",
    )
    parser.add_argument("--runtime-id", type=str, default="r1")
    parser.add_argument("--config", type=str, default="")
    parser.add_argument("--emit-plan-meta", type=int, default=1)

    parser.add_argument("--symbol", type=str, default="")
    parser.add_argument("--ticks-live", type=int, default=2)
    parser.add_argument("--ticks-sandbox", type=int, default=2)

    parser.add_argument("--min-events", type=int, default=1)
    parser.add_argument("--min-success-rate-improvement", type=float, default=-1.0)
    parser.add_argument("--max-consecutive-failures", type=int, default=99)

    parser.add_argument("--write-artifact", type=int, default=1)
    parser.add_argument("--write-summary", type=int, default=1)
    parser.add_argument("--write-decision", type=int, default=1)
    parser.add_argument("--write-manifest", type=int, default=1)
    parser.add_argument("--write-approved", type=int, default=1)
    parser.add_argument("--clean", action="store_true")

    # candidate config (kept for compatibility)
    parser.add_argument("--candidate-strategy-name", type=str, default="simple_strategy")
    parser.add_argument("--candidate-params-json", type=str, default="{}")

    args = parser.parse_args(argv)

    plan_path = Path(args.config) if args.config.strip() else None

    # Build a plan from defaults (or optional config), then apply CLI overrides
    if plan_path is not None:
        from config.loader import load_plan
        plan = load_plan(plan_path, runtime_id=args.runtime_id)
    else:
        plan = default_plan(runtime_id=args.runtime_id)

    # Optional symbol override: if provided, replace universe and strategy symbols
    sym = args.symbol.strip()
    if sym:
        plan = replace(plan, universe=replace(plan.universe, symbols=[sym]))
        strategies = []
        for s in plan.strategies:
            strategies.append(replace(s, symbols=[sym]))
        plan = replace(plan, strategies=strategies)

    # Ticks override
    plan = replace(
        plan,
        runtime=replace(
            plan.runtime,
            ticks_live=int(args.ticks_live),
            ticks_sandbox=int(args.ticks_sandbox),
        ),
    )

    # Promotion thresholds override
    plan = replace(
        plan,
        promotion=replace(
            plan.promotion,
            min_events=int(args.min_events),
            min_success_rate_improvement=float(args.min_success_rate_improvement),
            max_consecutive_failures=int(args.max_consecutive_failures),
        ),
    )

    # Artifact write toggle + per-artifact switches (backward compatible)
    write_artifact = int(args.write_artifact) == 1
    write_summary = int(getattr(args, "write_summary", 1)) == 1
    write_decision = int(getattr(args, "write_decision", 1)) == 1
    write_manifest = int(getattr(args, "write_manifest", 1)) == 1
    write_approved = int(getattr(args, "write_approved", 1)) == 1

    if not write_artifact:
        write_summary = False
        write_decision = False
        write_manifest = False
        write_approved = False

    plan = replace(
        plan,
        promotion=replace(
            plan.promotion,
            write_summary=write_summary,
            write_decision=write_decision,
            write_manifest=write_manifest,
            write_approved=write_approved,
        ),
    )

    # Candidate strategy name/params (best-effort, non-breaking)
    # For now, apply to the first strategy spec
    try:
        cand_params = json.loads(args.candidate_params_json)
        if not isinstance(cand_params, dict):
            cand_params = {}
    except Exception:
        cand_params = {}

    if plan.strategies:
        s0 = plan.strategies[0]
        s0 = replace(s0, name=args.candidate_strategy_name, params=dict(cand_params))
        plan = replace(plan, strategies=[s0, *plan.strategies[1:]])

    # Run orchestrator
    # Build plan_meta for audit/inspect/web (effective plan after overrides)
    plan_meta = None
    if int(getattr(args, "emit_plan_meta", 1)) == 1:
        plan_json = json.dumps(
            asdict(plan),
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        plan_meta = {
            "path": str(plan_path) if plan_path is not None else None,
            "sha256": hashlib.sha256(plan_json.encode("utf-8")).hexdigest(),
            "config": json.loads(plan_json),
        }

    resolved = resolve_plan(plan=plan, plan_meta=plan_meta)
    # run_local keeps timestamped candidate_id to avoid collisions and preserve audit semantics
    ts = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')
    candidate_id_override = f"cand_{resolved.runtime_id}_{ts}"
    result = orchestrate(
        resolved=resolved,
        clean=bool(args.clean),
        candidate_id_override=candidate_id_override,
    )

    # For compatibility, print decision payload if exists, else result
    if result.decision_path:
        payload = json.loads(Path(result.decision_path).read_text(encoding="utf-8"))
        decision = payload.get("decision") if isinstance(payload, dict) else None
        print("PromotionDecision:", json.dumps(decision, ensure_ascii=False, indent=2, default=str))
    else:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2, default=str))

    if result.approved_path:
        print("Approved artifact written:", result.approved_path)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
