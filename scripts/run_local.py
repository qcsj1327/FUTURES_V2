from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adapters.broker.simulated_broker import SimulatedBroker
from adapters.marketdata.simulated_market_data import SimulatedMarketData
from adapters.storage.datastore_fs import JSONLFileDataStore
from app.runtime_config import RuntimeConfig
from app.runtime_factory import RuntimeFactory
from optimize.promoter.approved_config import write_approved_config
from optimize.promoter.promote_from_datastore import promote_from_datastore
from optimize.promoter.promotion_gate import PromotionThresholds


def _utc_tag() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _rm_tree(path: Path) -> None:
    if not path.exists():
        return
    # python 3.13+: Path.unlink(missing_ok=True) exists, but we need recursive remove
    for p in sorted(path.rglob("*"), reverse=True):
        if p.is_file() or p.is_symlink():
            p.unlink()
        else:
            p.rmdir()
    path.rmdir()


def run_live(*, cfg: RuntimeConfig, ticks: int) -> None:
    md = SimulatedMarketData()
    broker = SimulatedBroker(md)

    rt = RuntimeFactory.build_live_runtime(
        config=cfg,
        market_data=md,
        broker=broker,
    )
    for _ in range(ticks):
        rt.run_market_once()


def run_sandbox(*, live_cfg: RuntimeConfig, ticks: int) -> None:
    # Build a live runtime first so sandbox can clone state and prefer live datastore snapshots
    md = SimulatedMarketData()
    broker = SimulatedBroker(md)
    live_rt = RuntimeFactory.build_live_runtime(
        config=live_cfg,
        market_data=md,
        broker=broker,
    )

    # Ensure at least one live tick exists so there is a snapshot baseline
    live_rt.run_market_once()

    sandbox_rt = RuntimeFactory.build_sandbox_runtime_from_live(live_rt)
    for _ in range(ticks):
        sandbox_rt.run_market_once()


def run_promote(
    *,
    cfg: RuntimeConfig,
    thresholds: PromotionThresholds,
    write_artifact: bool,
    candidate_strategy_name: str,
    candidate_params_json: str,
) -> Path | None:
    current_store = JSONLFileDataStore(
        root_dir=Path("data/store/live"),
        env="live",
        runtime_id=cfg.runtime_id,
    )
    candidate_store = JSONLFileDataStore(
        root_dir=Path("data/store/sandbox"),
        env="sandbox",
        runtime_id=cfg.runtime_id,
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
        json.dumps(
            asdict(decision),
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
    )

    if not write_artifact:
        return None

    candidate_id = f"cand_{cfg.runtime_id}_{_utc_tag()}"
    candidate_config: dict[str, Any] = {
        "strategy_name": candidate_strategy_name,
        "params": json.loads(candidate_params_json) if candidate_params_json else {},
    }

    out = write_approved_config(
        approved=decision.approved,
        candidate_id=candidate_id,
        candidate_config=candidate_config,
        decision_deltas=decision.deltas,
        thresholds=asdict(thresholds),
        filename=f"approved_{candidate_id}.json",
    )

    if out is None:
        print("Artifact: not written (decision not approved)")
    else:
        print("Artifact:", str(out))

    return out


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

    parser.add_argument("--min-events", type=int, default=50)
    parser.add_argument("--min-success-rate-improvement", type=float, default=0.01)
    parser.add_argument("--max-consecutive-failures", type=int, default=3)

    parser.add_argument(
        "--write-artifact",
        type=int,
        default=1,
        help="1 to write approved artifact, else 0",
    )
    parser.add_argument("--candidate-strategy-name", type=str, default="simple_strategy")
    parser.add_argument("--candidate-params-json", type=str, default="{}")

    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove data/store and data/artifacts/approved before run.",
    )
    args = parser.parse_args(argv)

    if args.clean:
        _rm_tree(Path("data/store"))
        _rm_tree(Path("data/artifacts/approved"))

    cfg = RuntimeConfig()
    thresholds = PromotionThresholds(
        min_events=args.min_events,
        min_success_rate_improvement=args.min_success_rate_improvement,
        max_consecutive_failures=args.max_consecutive_failures,
    )

    if args.mode in ("live", "all"):
        run_live(cfg=cfg, ticks=args.ticks_live)

    if args.mode in ("sandbox", "all"):
        run_sandbox(live_cfg=cfg, ticks=args.ticks_sandbox)

    artifact: Path | None = None
    if args.mode in ("promote", "all"):
        artifact = run_promote(
            cfg=cfg,
            thresholds=thresholds,
            write_artifact=bool(args.write_artifact),
            candidate_strategy_name=args.candidate_strategy_name,
            candidate_params_json=args.candidate_params_json,
        )

    # exit code: 0 always (this is a local runner), but print artifact path for convenience
    if artifact is not None:
        print("Approved artifact written:", artifact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
