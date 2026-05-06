from __future__ import annotations

import argparse
import json
import pickle
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.dashboard_projection import (
    OPTIONAL_ARTIFACT_WARNING_CODES,
    build_dashboard_projection,
)


@dataclass(frozen=True)
class StoreStats:
    fill_events_lines: int
    order_events_lines: int
    roll_events_lines: int
    rank_events_lines: int
    strategy_score_events_lines: int
    order_lifecycle_events_lines: int
    portfolio_snapshots_lines: int
    snapshot_pkls: int


def _read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected json object: {path}")
    return data


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for _ in f)


def _tail_jsonl(path: Path, n: int) -> list[dict[str, Any]]:
    if not path.exists() or n <= 0:
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-n:]
    out: list[dict[str, Any]] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def _jsonl_statuses(path: Path) -> list[str]:
    statuses: set[str] = set()
    for row in _tail_jsonl(path, 5000):
        status = row.get("status")
        if isinstance(status, str) and status:
            statuses.add(status)
    return sorted(statuses)


def _status_counts(path: Path) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in _tail_jsonl(path, 5000):
        status = row.get("status")
        if isinstance(status, str) and status:
            counter[status] += 1
    return dict(sorted(counter.items()))


def _pending_orders_count(path: Path) -> int:
    latest: dict[str, str] = {}
    for row in _tail_jsonl(path, 5000):
        order_id = row.get("order_id")
        status = row.get("status")
        if isinstance(order_id, str) and isinstance(status, str):
            latest[order_id] = status
    terminal = {"FILLED", "CANCELED", "EXPIRED", "REJECTED"}
    return sum(1 for status in latest.values() if status not in terminal)


def _top_lifecycle_reasons(
    path: Path,
    n: int,
    *,
    rejected_only: bool = False,
) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in _tail_jsonl(path, n):
        if rejected_only and row.get("status") != "REJECTED":
            continue
        reason = row.get("reason")
        if isinstance(reason, str) and reason:
            counter[reason] += 1
    return [{"reason": reason, "count": count} for reason, count in counter.most_common()]


def _portfolio_summary(store_dir: Path, portfolio: Any | None = None) -> dict[str, Any] | None:
    if portfolio is None:
        portfolio = _latest_portfolio(store_dir)
    if portfolio is None:
        return None
    metadata = getattr(portfolio, "metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}

    def _num(name: str) -> float | None:
        value = metadata.get(name)
        if isinstance(value, (int, float)):
            return float(value)
        attr = getattr(portfolio, name, None)
        return float(attr) if isinstance(attr, (int, float)) else None

    return {
        "equity": _num("equity"),
        "cash": _num("cash"),
        "margin_used": _num("margin_used"),
        "risk_ratio": _num("risk_ratio"),
        "unrealized_pnl": _num("unrealized_pnl"),
        "realized_pnl": _num("realized_pnl"),
        "max_risk_ratio_seen": _num("max_risk_ratio_seen"),
        "notional_by_symbol": metadata.get("notional_by_symbol", {}),
        "margin_by_symbol": metadata.get("margin_by_symbol", {}),
    }


def _latest_portfolio(store_dir: Path) -> Any | None:
    index_path = store_dir / "portfolio_snapshots.jsonl"
    if not index_path.exists():
        return None
    last: dict[str, Any] | None = None
    for row in _tail_jsonl(index_path, 5000):
        last = row
    if last is None:
        return None
    rel = last.get("portfolio_file")
    if not isinstance(rel, str) or not rel:
        return None
    path = store_dir / rel
    if not path.exists():
        return None
    with path.open("rb") as f:
        return pickle.load(f)


def _top_risk_reject_reasons(path: Path, n: int) -> list[dict[str, Any]]:
    return [
        item
        for item in _top_lifecycle_reasons(path, n, rejected_only=True)
        if str(item.get("reason", "")).startswith("risk_")
    ]


def _risk_stats(store_dir: Path, tail: int) -> dict[str, Any]:
    lifecycle_path = store_dir / "order_lifecycle_events.jsonl"
    risk_reasons = _top_risk_reject_reasons(lifecycle_path, tail)
    reject_count = sum(int(item["count"]) for item in risk_reasons)
    summary = _portfolio_summary(store_dir) or {}
    return {
        "reject_count": reject_count,
        "top_risk_reject_reasons": risk_reasons,
        "max_risk_ratio_seen": summary.get("max_risk_ratio_seen"),
    }


def _active_symbols_from_rank_events(path: Path) -> list[str]:
    events = _tail_jsonl(path, 5000)
    if not events:
        return []
    last = events[-1]
    active = last.get("active_symbols")
    if isinstance(active, list):
        return sorted(x for x in active if isinstance(x, str))
    scores = last.get("scores")
    if isinstance(scores, list):
        return sorted(
            item["symbol"]
            for item in scores
            if isinstance(item, dict) and isinstance(item.get("symbol"), str)
        )
    return []


def _enabled_strategies_from_plan(plan_cfg: dict[str, Any]) -> dict[str, list[str]]:
    out: dict[str, set[str]] = {}
    strategies = plan_cfg.get("strategies")
    if not isinstance(strategies, list):
        return {}
    for strategy in strategies:
        if not isinstance(strategy, dict):
            continue
        name = strategy.get("name")
        symbols = strategy.get("symbols")
        if not isinstance(name, str) or not isinstance(symbols, list):
            continue
        for sym in symbols:
            if isinstance(sym, str):
                out.setdefault(sym, set()).add(name)
    return {sym: sorted(names) for sym, names in sorted(out.items())}


def _enabled_strategies(
    approved: dict[str, Any] | None,
    plan_cfg: dict[str, Any],
) -> dict[str, list[str]]:
    if approved is not None:
        raw = approved.get("enabled_strategies_by_symbol")
        if isinstance(raw, dict):
            out: dict[str, list[str]] = {}
            for sym, names in raw.items():
                if isinstance(sym, str) and isinstance(names, list):
                    parsed = sorted(x for x in names if isinstance(x, str))
                    if parsed:
                        out[sym] = parsed
            return out
    return _enabled_strategies_from_plan(plan_cfg)


def _execution_observability(plan_cfg: dict[str, Any]) -> dict[str, Any]:
    adapters = plan_cfg.get("adapters")
    broker_cfg: dict[str, Any] = {}
    if isinstance(adapters, dict):
        raw_broker = adapters.get("broker")
        if isinstance(raw_broker, dict):
            broker_cfg = raw_broker
    broker_type = str(broker_cfg.get("mode", "simulated"))
    raw_params = broker_cfg.get("params")
    params = raw_params if isinstance(raw_params, dict) else {}
    submit_mode = str(params.get("submit_mode", "dry_run"))
    token = params.get("confirm_live_token")
    return {
        "execution_mode": submit_mode if submit_mode in {"dry_run", "live"} else "dry_run",
        "confirm_live": params.get("confirm_live") is True,
        "confirm_live_token_present": isinstance(token, str) and bool(token),
        "broker_type": broker_type,
    }


def _find_latest_manifest(*, runtime_id: str, manifests_dir: Path) -> Path | None:
    if not manifests_dir.exists():
        return None

    candidates: list[tuple[str, Path]] = []
    for p in manifests_dir.glob("manifest_*.json"):
        try:
            payload = _read_json(p)
        except Exception:
            continue
        if payload.get("kind") != "promotion_manifest":
            continue
        if str(payload.get("runtime_id", "")) != runtime_id:
            continue
        created = str(payload.get("created_at", ""))
        candidates.append((created, p))

    if not candidates:
        return None
    candidates.sort(key=lambda t: (t[0], t[1].name))
    return candidates[-1][1]


def _store_stats(store_dir: Path) -> StoreStats:
    snap_dir = store_dir / "snapshots"
    snap_pkls = len(list(snap_dir.glob("*.pkl"))) if snap_dir.exists() else 0
    return StoreStats(
        fill_events_lines=_count_lines(store_dir / "fill_events.jsonl"),
        order_events_lines=_count_lines(store_dir / "order_events.jsonl"),
        roll_events_lines=_count_lines(store_dir / "roll_events.jsonl"),
        rank_events_lines=_count_lines(store_dir / "rank_events.jsonl"),
        strategy_score_events_lines=_count_lines(store_dir / "strategy_score_events.jsonl"),
        order_lifecycle_events_lines=_count_lines(store_dir / "order_lifecycle_events.jsonl"),
        portfolio_snapshots_lines=_count_lines(store_dir / "portfolio_snapshots.jsonl"),
        snapshot_pkls=snap_pkls,
    )


def inspect_run(
    *,
    runtime_id: str,
    store_root: Path = Path("data/store"),
    artifacts_root: Path = Path("data/artifacts"),
    tail: int = 5,
) -> dict[str, Any]:
    manifests_dir = artifacts_root / "manifests"
    manifest_path = _find_latest_manifest(runtime_id=runtime_id, manifests_dir=manifests_dir)
    if manifest_path is None:
        raise FileNotFoundError(f"no manifest found for runtime_id={runtime_id} in {manifests_dir}")

    manifest = _read_json(manifest_path)

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}

    plan_meta = manifest.get("plan")
    if not isinstance(plan_meta, dict):
        plan_meta = {}

    plan_cfg_any = plan_meta.get("config")
    plan_cfg: dict[str, Any] = plan_cfg_any if isinstance(plan_cfg_any, dict) else {}
    warnings: list[str] = []

    def _maybe_read(path_str: Any, name: str) -> dict[str, Any] | None:
        if not isinstance(path_str, str) or not path_str:
            warnings.append(f"missing_{name}")
            return None
        p = Path(path_str)
        if not p.exists():
            warnings.append(f"missing_{name}")
            warnings.append(f"missing_{name}_file:{p}")
            return None
        try:
            return _read_json(p)
        except Exception as exc:
            warnings.append(f"invalid_{name}_file:{p}:{exc.__class__.__name__}")
            return None

    current_summary = _maybe_read(artifacts.get("current_summary"), "current_summary")
    candidate_summary = _maybe_read(artifacts.get("candidate_summary"), "candidate_summary")
    decision = _maybe_read(artifacts.get("decision"), "decision")
    approved = _maybe_read(artifacts.get("approved"), "approved")
    strategy_switch_proposal = _maybe_read(
        artifacts.get("strategy_switch_proposal")
        or str(artifacts_root / "strategy_switch" / f"strategy_switch_proposal_{runtime_id}.json"),
        "strategy_switch_proposal",
    )
    strategy_switch_approved = _maybe_read(
        artifacts.get("strategy_switch_approved")
        or str(artifacts_root / "strategy_switch" / f"strategy_switch_approved_{runtime_id}.json"),
        "strategy_switch_approved",
    )

    live_dir = store_root / "live" / runtime_id
    sandbox_dir = store_root / "sandbox" / runtime_id
    live_portfolio = _latest_portfolio(live_dir)
    sandbox_portfolio = _latest_portfolio(sandbox_dir)
    live_portfolio_summary = _portfolio_summary(live_dir, live_portfolio)
    sandbox_portfolio_summary = _portfolio_summary(sandbox_dir, sandbox_portfolio)
    live_lifecycle_events = _tail_jsonl(live_dir / "order_lifecycle_events.jsonl", tail)
    sandbox_lifecycle_events = _tail_jsonl(sandbox_dir / "order_lifecycle_events.jsonl", tail)
    live_order_events = _tail_jsonl(live_dir / "order_events.jsonl", tail)
    sandbox_order_events = _tail_jsonl(sandbox_dir / "order_events.jsonl", tail)
    live_fill_events = _tail_jsonl(live_dir / "fill_events.jsonl", tail)
    sandbox_fill_events = _tail_jsonl(sandbox_dir / "fill_events.jsonl", tail)
    live_rank_events = _tail_jsonl(live_dir / "rank_events.jsonl", tail)
    sandbox_rank_events = _tail_jsonl(sandbox_dir / "rank_events.jsonl", tail)
    event_stats = {
        "live": _store_stats(live_dir).__dict__,
        "sandbox": _store_stats(sandbox_dir).__dict__,
    }
    lifecycle_stats = {
        "live": {
            "status_counts": _status_counts(live_dir / "order_lifecycle_events.jsonl"),
            "top_reasons": _top_lifecycle_reasons(
                live_dir / "order_lifecycle_events.jsonl",
                5000,
            )[:10],
        },
        "sandbox": {
            "status_counts": _status_counts(sandbox_dir / "order_lifecycle_events.jsonl"),
            "top_reasons": _top_lifecycle_reasons(
                sandbox_dir / "order_lifecycle_events.jsonl",
                5000,
            )[:10],
        },
    }
    risk_stats = {
        "live": _risk_stats(live_dir, tail),
        "sandbox": _risk_stats(sandbox_dir, tail),
    }
    top_lifecycle_reject_reasons = {
        "live": _top_lifecycle_reasons(
            live_dir / "order_lifecycle_events.jsonl",
            tail,
            rejected_only=True,
        ),
        "sandbox": _top_lifecycle_reasons(
            sandbox_dir / "order_lifecycle_events.jsonl",
            tail,
            rejected_only=True,
        ),
    }
    execution = _execution_observability(plan_cfg)
    enabled_strategies_by_symbol = {
        "live": _enabled_strategies(strategy_switch_approved, plan_cfg),
        "sandbox": _enabled_strategies(strategy_switch_approved, plan_cfg),
    }
    dashboard_projection = build_dashboard_projection(
        runtime_id=runtime_id,
        plan_cfg=plan_cfg,
        execution=execution,
        portfolio={
            "live": live_portfolio_summary,
            "sandbox": sandbox_portfolio_summary,
        },
        latest_portfolios={
            "live": live_portfolio,
            "sandbox": sandbox_portfolio,
        },
        event_stats=event_stats,
        lifecycle_events={
            "live": _tail_jsonl(live_dir / "order_lifecycle_events.jsonl", 5000),
            "sandbox": _tail_jsonl(sandbox_dir / "order_lifecycle_events.jsonl", 5000),
        },
        order_events={
            "live": _tail_jsonl(live_dir / "order_events.jsonl", 5000),
            "sandbox": _tail_jsonl(sandbox_dir / "order_events.jsonl", 5000),
        },
        fill_events={
            "live": _tail_jsonl(live_dir / "fill_events.jsonl", 5000),
            "sandbox": _tail_jsonl(sandbox_dir / "fill_events.jsonl", 5000),
        },
        rank_events={
            "live": _tail_jsonl(live_dir / "rank_events.jsonl", 5000),
            "sandbox": _tail_jsonl(sandbox_dir / "rank_events.jsonl", 5000),
        },
        lifecycle_stats=lifecycle_stats,
        risk_stats=risk_stats,
        top_lifecycle_reject_reasons=top_lifecycle_reject_reasons,
        strategy_switch_proposal=strategy_switch_proposal,
        strategy_switch_approved=strategy_switch_approved,
        enabled_strategies_by_symbol=enabled_strategies_by_symbol,
        warning_codes=warnings,
    )
    optional_warnings = [
        code
        for code in warnings
        if code in OPTIONAL_ARTIFACT_WARNING_CODES
        or code.startswith(tuple(f"{x}_file:" for x in OPTIONAL_ARTIFACT_WARNING_CODES))
    ]
    main_warnings = [
        code
        for code in warnings
        if code not in optional_warnings
    ]

    out: dict[str, Any] = {
        "runtime_id": runtime_id,
        "manifest": {
            "path": str(manifest_path),
            "created_at": manifest.get("created_at"),
            "candidate_id": manifest.get("candidate_id"),
        },
        "event_stats": event_stats,
        "event_statuses": {
            "live_order_lifecycle_statuses": _jsonl_statuses(
                live_dir / "order_lifecycle_events.jsonl",
            ),
            "sandbox_order_lifecycle_statuses": _jsonl_statuses(
                sandbox_dir / "order_lifecycle_events.jsonl",
            ),
        },
        "live_order_lifecycle_status_counts": _status_counts(
            live_dir / "order_lifecycle_events.jsonl",
        ),
        "sandbox_order_lifecycle_status_counts": _status_counts(
            sandbox_dir / "order_lifecycle_events.jsonl",
        ),
        "pending_orders_count": {
            "live": _pending_orders_count(live_dir / "order_lifecycle_events.jsonl"),
            "sandbox": _pending_orders_count(sandbox_dir / "order_lifecycle_events.jsonl"),
        },
        "execution": execution,
        "portfolio": {
            "live": live_portfolio_summary,
            "sandbox": sandbox_portfolio_summary,
        },
        "top_risk_reject_reasons": {
            "live": _top_risk_reject_reasons(live_dir / "order_lifecycle_events.jsonl", tail),
            "sandbox": _top_risk_reject_reasons(sandbox_dir / "order_lifecycle_events.jsonl", tail),
        },
        "risk_stats": risk_stats,
        "active_symbols": {
            "live": _active_symbols_from_rank_events(live_dir / "rank_events.jsonl"),
            "sandbox": _active_symbols_from_rank_events(sandbox_dir / "rank_events.jsonl"),
        },
        "enabled_strategies_by_symbol": {
            "live": enabled_strategies_by_symbol["live"],
            "sandbox": enabled_strategies_by_symbol["sandbox"],
        },
        "top_lifecycle_reject_reasons": top_lifecycle_reject_reasons,
        "live_top_lifecycle_reasons": _top_lifecycle_reasons(
            live_dir / "order_lifecycle_events.jsonl",
            5000,
        )[:10],
        "sandbox_top_lifecycle_reasons": _top_lifecycle_reasons(
            sandbox_dir / "order_lifecycle_events.jsonl",
            5000,
        )[:10],
        "lifecycle_stats": lifecycle_stats,
        "event_tail": {
            "live_order_lifecycle_events": live_lifecycle_events,
            "sandbox_order_lifecycle_events": sandbox_lifecycle_events,
        },
        "plan": {
            "path": plan_meta.get("path"),
            "sha256": plan_meta.get("sha256"),
            "router": plan_cfg.get("router"),
            "universe": plan_cfg.get("universe"),
            "strategies": plan_cfg.get("strategies"),
        },
        "summaries": {"current": current_summary, "candidate": candidate_summary},
        "decision": decision,
        "approved": approved,
        "strategy_switch": {
            "proposal": strategy_switch_proposal,
            "approved": strategy_switch_approved,
        },
        "warnings": main_warnings,
        "optional_warnings": optional_warnings,
        "dashboard_projection": dashboard_projection,
        "stores": {
            "live": {
                "dir": str(live_dir),
                "stats": _store_stats(live_dir).__dict__,
                "tail": {
                    "fill_events": live_fill_events,
                    "order_events": live_order_events,
                    "roll_events": _tail_jsonl(live_dir / "roll_events.jsonl", tail),
                    "rank_events": live_rank_events,
                    "strategy_score_events": _tail_jsonl(
                        live_dir / "strategy_score_events.jsonl",
                        tail,
                    ),
                    "order_lifecycle_events": live_lifecycle_events,
                },
            },
            "sandbox": {
                "dir": str(sandbox_dir),
                "stats": _store_stats(sandbox_dir).__dict__,
                "tail": {
                    "fill_events": sandbox_fill_events,
                    "order_events": sandbox_order_events,
                    "roll_events": _tail_jsonl(sandbox_dir / "roll_events.jsonl", tail),
                    "rank_events": sandbox_rank_events,
                    "strategy_score_events": _tail_jsonl(
                        sandbox_dir / "strategy_score_events.jsonl",
                        tail,
                    ),
                    "order_lifecycle_events": sandbox_lifecycle_events,
                },
            },
        },
    }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="inspect_run",
        description="Inspect a run by runtime_id (read-only).",
    )
    parser.add_argument("runtime_id", type=str)
    parser.add_argument("--store-root", type=str, default="data/store")
    parser.add_argument("--artifacts-root", type=str, default="data/artifacts")
    parser.add_argument("--tail", type=int, default=5)
    args = parser.parse_args(argv)

    report = inspect_run(
        runtime_id=args.runtime_id,
        store_root=Path(args.store_root),
        artifacts_root=Path(args.artifacts_root),
        tail=args.tail,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
