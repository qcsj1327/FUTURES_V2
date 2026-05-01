from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_fs import JSONLFileDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
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
        description="Run live/sandbox/promote locally.",
    )
    parser.add_argument(
        "mode",
        nargs="?",
        default="all",
        choices=["live", "sandbox", "promote", "all"],
        help="Which pipeline to run.",
    )

    parser.add_argument("--ticks-live", type=int, default=5)
    parser.add_argument("--ticks-sandbox", type=int, default=5)

    parser.add_argument(
        "--runtime-id",
        type=str,
        default="auto",
        help="Runtime ID. Use 'auto' to generate a fresh id per run.",
    )
    parser.add_argument("--symbol", type=str, default=None)

    parser.add_argument("--store-root", type=str, default="data/store")
    parser.add_argument("--approved-dir", type=str, default="data/artifacts/approved")
    parser.add_argument("--decision-dir", type=str, default="data/artifacts/decisions")
    parser.add_argument("--summary-dir", type=str, default="data/artifacts/summaries")
    parser.add_argument("--manifest-dir", type=str, default="data/artifacts/manifests")

    parser.add_argument("--min-events", type=int, default=50)
    parser.add_argument("--min-success-rate-improvement", type=float, default=0.01)
    parser.add_argument("--max-consecutive-failures", type=int, default=3)

    parser.add_argument("--write-summary", type=int, default=1)
    parser.add_argument("--write-decision", type=int, default=1)
    parser.add_argument("--write-manifest", type=int, default=1)
    parser.add_argument("--write-artifact", type=int, default=1)

    parser.add_argument("--candidate-strategy-name", type=str, default="simple_strategy")
    parser.add_argument("--candidate-params-json", type=str, default="{}")

    parser.add_argument("--clean", action="store_true")
    args = parser.parse_args(argv)

    store_root = Path(args.store_root)
    approved_dir = Path(args.approved_dir)
    decision_dir = Path(args.decision_dir)
    summary_dir = Path(args.summary_dir)
    manifest_dir = Path(args.manifest_dir)

    if args.clean:
        _rm_tree(store_root)
        _rm_tree(approved_dir)
        _rm_tree(decision_dir)
        _rm_tree(summary_dir)
        _rm_tree(manifest_dir)

    runtime_id = args.runtime_id
    if runtime_id == "auto":
        runtime_id = f"r_{_utc_tag()}"

    cfg = _make_config(runtime_id=runtime_id, symbol=args.symbol)

    thresholds = PromotionThresholds(
        min_events=args.min_events,
        min_success_rate_improvement=args.min_success_rate_improvement,
        max_consecutive_failures=args.max_consecutive_failures,
    )

    if args.mode in ("live", "all"):
        run_live(cfg=cfg, ticks=args.ticks_live)

    if args.mode in ("sandbox", "all"):
        run_sandbox(live_cfg=cfg, ticks=args.ticks_sandbox)

    if args.mode in ("promote", "all"):
        run_promote(
            cfg=cfg,
            thresholds=thresholds,
            candidate_strategy_name=args.candidate_strategy_name,
            candidate_params_json=args.candidate_params_json,
            store_root=store_root,
            approved_dir=approved_dir,
            decision_dir=decision_dir,
            summary_dir=summary_dir,
            manifest_dir=manifest_dir,
            write_summary=bool(args.write_summary),
            write_decision=bool(args.write_decision),
            write_artifact=bool(args.write_artifact),
            write_manifest=bool(args.write_manifest),
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
