from __future__ import annotations

import argparse
import json
import pickle
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from web.readmodel.audit import load_audit_projection
from web.readmodel.dashboard_projection import (
    OPTIONAL_ARTIFACT_WARNING_CODES,
    RUNTIME_SCOPES,
    build_dashboard_projection,
)
from web.readmodel.event_rows import CANONICAL_SCOPES, read_valid_event_rows


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


def _tail_jsonl(path: Path, n: int, *, scope: str) -> list[dict[str, Any]]:
    return read_valid_event_rows(path, expected_scope=scope, tail=n).rows


def _invalid_event_summary(path: Path, n: int, *, scope: str) -> dict[str, Any]:
    result = read_valid_event_rows(path, expected_scope=scope, tail=n)
    return {
        "invalid_count": result.invalid_count,
        "invalid_reasons": result.invalid_reasons,
    }


def _jsonl_statuses(path: Path, *, scope: str) -> list[str]:
    statuses: set[str] = set()
    for row in _tail_jsonl(path, 5000, scope=scope):
        status = row.get("status")
        if isinstance(status, str) and status:
            statuses.add(status)
    return sorted(statuses)


def _status_counts(path: Path, *, scope: str) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in _tail_jsonl(path, 5000, scope=scope):
        status = row.get("status")
        if isinstance(status, str) and status:
            counter[status] += 1
    return dict(sorted(counter.items()))


def _pending_orders_count(path: Path, *, scope: str) -> int:
    latest: dict[str, str] = {}
    for row in _tail_jsonl(path, 5000, scope=scope):
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
    scope: str,
    rejected_only: bool = False,
) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in _tail_jsonl(path, n, scope=scope):
        if rejected_only and row.get("status") != "REJECTED":
            continue
        reason = row.get("reason")
        if isinstance(reason, str) and reason:
            counter[reason] += 1
    return [{"reason": reason, "count": count} for reason, count in counter.most_common()]


def _portfolio_summary(
    store_dir: Path,
    *,
    scope: str,
    portfolio: Any | None = None,
    metrics: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if portfolio is None:
        portfolio = _latest_portfolio(store_dir, scope=scope)
    if portfolio is None and metrics is None:
        return None
    metadata = getattr(portfolio, "metadata", {})
    metadata = metadata if isinstance(metadata, dict) else {}
    metrics = metrics if isinstance(metrics, dict) else {}

    def _num(name: str) -> float | None:
        value = metadata.get(name)
        if isinstance(value, (int, float)):
            return float(value)
        attr = getattr(portfolio, name, None)
        if isinstance(attr, (int, float)):
            return float(attr)
        metric_value = metrics.get(name)
        return float(metric_value) if isinstance(metric_value, (int, float)) else None

    return {
        "equity": _num("equity"),
        "cash": _num("cash"),
        "margin_used": _num("margin_used"),
        "risk_ratio": _num("risk_ratio"),
        "unrealized_pnl": _num("unrealized_pnl"),
        "realized_pnl": _num("realized_pnl"),
        "max_risk_ratio_seen": _num("max_risk_ratio_seen"),
        "notional_by_symbol": metadata.get(
            "notional_by_symbol",
            metrics.get("notional_by_symbol", {}),
        ),
        "margin_by_symbol": metadata.get("margin_by_symbol", metrics.get("margin_by_symbol", {})),
        "unrealized_pnl_by_symbol": metadata.get(
            "unrealized_pnl_by_symbol",
            metrics.get("unrealized_pnl_by_symbol", {}),
        ),
    }


def _latest_portfolio(store_dir: Path, *, scope: str) -> Any | None:
    index_path = store_dir / "portfolio_snapshots.jsonl"
    if not index_path.exists():
        return None
    last: dict[str, Any] | None = None
    for row in _tail_jsonl(index_path, 5000, scope=scope):
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


def _latest_metrics_summary(store_dir: Path, *, scope: str) -> dict[str, Any] | None:
    last: dict[str, Any] | None = None
    for row in _tail_jsonl(store_dir / "metrics.jsonl", 5000, scope=scope):
        metrics = row.get("metrics")
        if isinstance(metrics, dict):
            last = metrics
    return last


def _top_risk_reject_reasons(path: Path, n: int, *, scope: str) -> list[dict[str, Any]]:
    return [
        item
        for item in _top_lifecycle_reasons(path, n, scope=scope, rejected_only=True)
        if str(item.get("reason", "")).startswith("risk_")
    ]


def _risk_stats(store_dir: Path, tail: int, *, scope: str) -> dict[str, Any]:
    lifecycle_path = store_dir / "order_lifecycle_events.jsonl"
    risk_reasons = _top_risk_reject_reasons(lifecycle_path, tail, scope=scope)
    reject_count = sum(int(item["count"]) for item in risk_reasons)
    summary = (
        _portfolio_summary(
            store_dir,
            scope=scope,
            metrics=_latest_metrics_summary(store_dir, scope=scope),
        )
        or {}
    )
    return {
        "reject_count": reject_count,
        "top_risk_reject_reasons": risk_reasons,
        "max_risk_ratio_seen": summary.get("max_risk_ratio_seen"),
    }


def _active_symbols_from_rank_events(path: Path, *, scope: str) -> list[str]:
    events = _tail_jsonl(path, 5000, scope=scope)
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
    switch_cfg = plan_cfg.get("strategy_switch")
    if isinstance(switch_cfg, dict):
        raw_enabled = switch_cfg.get("enabled_by_symbol")
        if isinstance(raw_enabled, dict):
            out_enabled: dict[str, list[str]] = {}
            for sym, names in raw_enabled.items():
                if isinstance(sym, str) and isinstance(names, list):
                    parsed = sorted({name for name in names if isinstance(name, str)})
                    if parsed:
                        out_enabled[sym] = parsed
            if out_enabled:
                return out_enabled

    out: dict[str, set[str]] = {}
    strategies = plan_cfg.get("strategies")
    if not isinstance(strategies, list):
        return {}
    universe = plan_cfg.get("universe")
    default_strategy_symbols = (
        universe.get("symbols")
        if isinstance(universe, dict) and isinstance(universe.get("symbols"), list)
        else []
    )
    for strategy in strategies:
        if not isinstance(strategy, dict):
            continue
        name = strategy.get("name")
        symbols = strategy.get("symbols", default_strategy_symbols)
        if not isinstance(name, str) or not isinstance(symbols, list):
            continue
        for sym in symbols:
            if isinstance(sym, str):
                out.setdefault(sym, set()).add(name)
    first_enabled: dict[str, list[str]] = {}
    for sym, names in sorted(out.items()):
        if names:
            first_enabled[sym] = [sorted(names)[0]]
    return first_enabled


def _minimal_effective_plan_cfg() -> dict[str, Any]:
    return {
        "universe": {"symbols": []},
        "strategies": [],
        "runtime": {},
        "adapters": {},
    }


def _effective_plan_cfg(plan_cfg: dict[str, Any]) -> dict[str, Any]:
    effective = dict(plan_cfg)
    universe = effective.get("universe")
    if not isinstance(universe, dict) or not isinstance(universe.get("symbols"), list):
        effective["universe"] = {"symbols": []}
    return effective


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _plan_cfg_from_manifest(manifest: dict[str, Any], plan_meta: dict[str, Any]) -> dict[str, Any]:
    if isinstance(plan_meta.get("config"), dict):
        raise ValueError("invalid_manifest_schema:plan.config")
    plan_cfg_any = plan_meta.get("effective_config_summary")
    if not isinstance(plan_cfg_any, dict):
        raise ValueError("invalid_manifest_schema:missing_effective_config_summary")
    plan_cfg = _effective_plan_cfg(plan_cfg_any if isinstance(plan_cfg_any, dict) else {})

    runtime_profile = _manifest_scope(manifest)
    runtime = plan_cfg.get("runtime")
    runtime = dict(runtime) if isinstance(runtime, dict) else {}
    mode = _str_or_none(runtime.get("mode"))
    if mode != runtime_profile:
        raise ValueError(f"invalid_manifest_schema:runtime_mode_mismatch:{mode}:{runtime_profile}")
    plan_cfg["runtime"] = runtime
    return plan_cfg


def _manifest_scope(manifest: dict[str, Any]) -> str:
    runtime_profile = _str_or_none(manifest.get("runtime_profile"))
    datastore_scope = _str_or_none(manifest.get("datastore_scope"))
    if runtime_profile not in CANONICAL_SCOPES:
        raise ValueError(f"invalid_manifest_schema:runtime_profile:{runtime_profile}")
    if datastore_scope not in CANONICAL_SCOPES:
        raise ValueError(f"invalid_manifest_schema:datastore_scope:{datastore_scope}")
    if runtime_profile != datastore_scope:
        raise ValueError(
            f"invalid_manifest_schema:profile_scope_mismatch:{runtime_profile}:{datastore_scope}"
        )
    is_live = manifest.get("is_live")
    if isinstance(is_live, bool) and is_live is not (runtime_profile == "live"):
        raise ValueError(f"invalid_manifest_schema:is_live_mismatch:{runtime_profile}")
    return runtime_profile


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


def _scoped_artifact_or_none(
    payload: dict[str, Any] | None,
    *,
    expected_scope: str,
    warnings: list[str],
    name: str,
) -> dict[str, Any] | None:
    if payload is None:
        return None
    runtime_profile = _str_or_none(payload.get("runtime_profile"))
    datastore_scope = _str_or_none(payload.get("datastore_scope"))
    if runtime_profile != expected_scope or datastore_scope != expected_scope:
        warnings.append(f"invalid_{name}_scope")
        return None
    is_live = payload.get("is_live")
    if isinstance(is_live, bool) and is_live is not (expected_scope == "live"):
        warnings.append(f"invalid_{name}_is_live")
        return None
    return payload


def _execution_observability(plan_cfg: dict[str, Any]) -> dict[str, Any]:
    runtime_cfg: dict[str, Any] = {}
    raw_runtime = plan_cfg.get("runtime")
    if isinstance(raw_runtime, dict):
        runtime_cfg = raw_runtime
    runtime_mode = str(runtime_cfg.get("mode", "local"))
    adapters = plan_cfg.get("adapters")
    broker_cfg: dict[str, Any] = {}
    if isinstance(adapters, dict):
        raw_broker = adapters.get("broker")
        if isinstance(raw_broker, dict):
            broker_cfg = raw_broker
    default_broker = "tqkq" if runtime_mode in {"dryrun", "live"} else "simulated"
    broker_type = str(broker_cfg.get("mode", default_broker))
    raw_params = broker_cfg.get("params")
    params = raw_params if isinstance(raw_params, dict) else {}
    if runtime_mode == "local":
        execution_mode = "simulated"
    else:
        submit_mode = str(
            params.get(
                "submit_mode",
                broker_cfg.get("submit_mode", "live" if runtime_mode == "live" else "dryrun"),
            )
        )
        execution_mode = submit_mode if submit_mode in {"dryrun", "live"} else "dryrun"
    token = params.get("confirm_live_token", broker_cfg.get("confirm_live_token"))
    return {
        "execution_mode": execution_mode,
        "confirm_live": params.get("confirm_live", broker_cfg.get("confirm_live")) is True,
        "confirm_live_token_present": _token_present(token),
        "broker_type": broker_type,
    }


def _token_present(value: object) -> bool:
    if isinstance(value, str):
        return bool(value)
    if isinstance(value, dict):
        return value.get("present") is True
    return False


def _find_latest_manifest(*, runtime_id: str, manifests_dir: Path) -> Path | None:
    if not manifests_dir.exists():
        return None

    candidates: list[tuple[str, Path]] = []
    for p in manifests_dir.glob(f"manifest_{runtime_id}_*.json"):
        payload = _read_json(p)
        if payload.get("kind") != "promotion_manifest":
            raise ValueError(f"invalid manifest kind in {p}")
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


def _empty_store_stats() -> dict[str, int]:
    return StoreStats(
        fill_events_lines=0,
        order_events_lines=0,
        roll_events_lines=0,
        rank_events_lines=0,
        strategy_score_events_lines=0,
        order_lifecycle_events_lines=0,
        portfolio_snapshots_lines=0,
        snapshot_pkls=0,
    ).__dict__


def _fail_closed_report(
    *,
    runtime_id: str,
    reason: str,
    manifest_path: Path | None,
    store_root: Path,
) -> dict[str, Any]:
    event_stats = {scope: _empty_store_stats() for scope in RUNTIME_SCOPES}
    empty_counts: dict[str, dict[str, Any]] = {scope: {} for scope in RUNTIME_SCOPES}
    empty_lists: dict[str, list[Any]] = {scope: [] for scope in RUNTIME_SCOPES}
    empty_positions = {
        scope: {
            "runtime_profile": scope,
            "datastore_scope": scope,
            "source": "portfolio_snapshot",
            "source_event_ids": [],
            "source_scope_unknown": False,
            "source_scope_unknown_count": 0,
            "invalid_projection_source_count": 0,
            "payload_types": [],
            "event_sources": [],
            "items": [],
            "empty_reason": "fail_closed",
            "is_source_of_truth": True,
        }
        for scope in RUNTIME_SCOPES
    }
    projection = {
        "schema_version": 1,
        "runtime_id": runtime_id,
        "fail_closed": True,
        "fail_closed_reasons": [reason],
        "execution_state": {
            "runtime_mode": None,
            "runtime_profile": None,
            "datastore_scope": None,
            "source": "fail_closed",
        },
        "portfolio": {scope: None for scope in RUNTIME_SCOPES},
        "positions": empty_positions,
        "broker_sync_diagnostics": {
            scope: {
                "runtime_profile": scope,
                "datastore_scope": scope,
                "source": "broker_sync_observation",
                "source_event_ids": [],
                "items": [],
                "count": 0,
                "is_source_of_truth": False,
                "empty_reason": "fail_closed",
            }
            for scope in RUNTIME_SCOPES
        },
        "pending_orders": {
            scope: {"runtime_profile": scope, "datastore_scope": scope, "items": [], "count": 0}
            for scope in RUNTIME_SCOPES
        },
        "order_status": {
            scope: {
                "runtime_profile": scope,
                "datastore_scope": scope,
                "counts": {},
                "items": [],
                "count": 0,
            }
            for scope in RUNTIME_SCOPES
        },
        "quotes": {
            scope: {
                "runtime_profile": scope,
                "datastore_scope": scope,
                "items": [],
                "by_symbol": {},
                "by_contract": {},
            }
            for scope in RUNTIME_SCOPES
        },
        "lifecycle_view": {
            scope: {"runtime_profile": scope, "datastore_scope": scope, "items": []}
            for scope in RUNTIME_SCOPES
        },
        "strategy_scores": {
            scope: {
                "runtime_profile": scope,
                "datastore_scope": scope,
                "items": [],
                "latest_by_symbol": {},
            }
            for scope in RUNTIME_SCOPES
        },
        "lifecycle_summary": empty_counts,
        "risk_summary": {scope: {"top_risk_reject_reasons": []} for scope in RUNTIME_SCOPES},
        "alerts": {
            "items": [{"code": reason, "level": "error", "message": reason, "source": "readmodel"}],
            "optional_warnings": [],
            "counts": {"error": 1, "warning": 0, "info": 0},
        },
        "active_symbols": {
            scope: {
                "runtime_profile": scope,
                "datastore_scope": scope,
                "items": [],
                "source": "fail_closed",
            }
            for scope in RUNTIME_SCOPES
        },
        "strategy_switch": {
            "state": "invalid_source",
            "proposal": None,
            "approved": None,
            "rejected": None,
            "enabled_strategies_by_symbol": {},
        },
    }
    scope_dirs = {scope: store_root / scope / runtime_id for scope in RUNTIME_SCOPES}
    return {
        "runtime_id": runtime_id,
        "fail_closed": True,
        "fail_closed_reasons": [reason],
        "manifest": {
            "path": str(manifest_path) if manifest_path is not None else None,
            "created_at": None,
            "candidate_id": None,
            "status": "invalid_source",
        },
        "event_stats": event_stats,
        "event_statuses": empty_lists,
        "order_lifecycle_status_counts": empty_counts,
        "pending_orders_count": {scope: 0 for scope in RUNTIME_SCOPES},
        "execution": projection["execution_state"],
        "portfolio": {scope: None for scope in RUNTIME_SCOPES},
        "top_risk_reject_reasons": empty_lists,
        "risk_stats": {scope: {} for scope in RUNTIME_SCOPES},
        "active_symbols": empty_lists,
        "enabled_strategies_by_symbol": {scope: {} for scope in RUNTIME_SCOPES},
        "top_lifecycle_reject_reasons": empty_lists,
        "top_lifecycle_reasons": empty_lists,
        "lifecycle_stats": empty_counts,
        "event_tail": {scope: {"order_lifecycle_events": []} for scope in RUNTIME_SCOPES},
        "plan": {
            "path": None,
            "sha256": None,
            "effective_config_summary": {},
            "redaction_status": None,
        },
        "summaries": {"current": None, "candidate": None},
        "decision": None,
        "approved": None,
        "strategy_switch": {"proposal": None, "approved": None, "rejected": None},
        "warnings": [reason],
        "optional_warnings": [],
        "invalid_event_sources": {scope: {} for scope in RUNTIME_SCOPES},
        "dashboard_projection": projection,
        "stores": {
            scope: {
                "dir": str(scope_dirs[scope]),
                "stats": _empty_store_stats(),
                "tail": {
                    "fill_events": [],
                    "order_events": [],
                    "roll_events": [],
                    "rank_events": [],
                    "strategy_score_events": [],
                    "order_lifecycle_events": [],
                },
            }
            for scope in RUNTIME_SCOPES
        },
    }


def inspect_run(
    *,
    runtime_id: str,
    store_root: Path = Path("data/store"),
    artifacts_root: Path = Path("data/artifacts"),
    tail: int = 5,
) -> dict[str, Any]:
    manifests_dir = artifacts_root / "manifests"
    warnings: list[str] = []
    manifest_path = _find_latest_manifest(runtime_id=runtime_id, manifests_dir=manifests_dir)
    if manifest_path is None:
        return _fail_closed_report(
            runtime_id=runtime_id,
            reason="missing_manifest",
            manifest_path=None,
            store_root=store_root,
        )
    manifest = _read_json(manifest_path)

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}

    plan_meta = manifest.get("plan")
    if not isinstance(plan_meta, dict):
        plan_meta = {}

    try:
        manifest_scope = _manifest_scope(manifest)
        plan_cfg = _plan_cfg_from_manifest(manifest, plan_meta)
    except ValueError as exc:
        return _fail_closed_report(
            runtime_id=runtime_id,
            reason=str(exc),
            manifest_path=manifest_path,
            store_root=store_root,
        )

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
        artifacts.get("strategy_switch_proposal"),
        "strategy_switch_proposal",
    )
    strategy_switch_approved = _maybe_read(
        artifacts.get("strategy_switch_approved"),
        "strategy_switch_approved",
    )
    strategy_switch_rejected = _maybe_read(
        artifacts.get("strategy_switch_rejected"),
        "strategy_switch_rejected",
    )
    strategy_switch_proposal = _scoped_artifact_or_none(
        strategy_switch_proposal,
        expected_scope=manifest_scope,
        warnings=warnings,
        name="strategy_switch_proposal",
    )
    strategy_switch_approved = _scoped_artifact_or_none(
        strategy_switch_approved,
        expected_scope=manifest_scope,
        warnings=warnings,
        name="strategy_switch_approved",
    )
    strategy_switch_rejected = _scoped_artifact_or_none(
        strategy_switch_rejected,
        expected_scope=manifest_scope,
        warnings=warnings,
        name="strategy_switch_rejected",
    )

    scope_dirs = {scope: store_root / scope / runtime_id for scope in RUNTIME_SCOPES}
    latest_portfolios = {
        scope: _latest_portfolio(path, scope=scope) for scope, path in scope_dirs.items()
    }
    latest_metrics = {
        scope: _latest_metrics_summary(path, scope=scope) for scope, path in scope_dirs.items()
    }
    portfolio_summaries = {
        scope: _portfolio_summary(
            scope_dirs[scope],
            scope=scope,
            portfolio=latest_portfolios[scope],
            metrics=latest_metrics[scope],
        )
        for scope in RUNTIME_SCOPES
    }
    lifecycle_tail = {
        scope: _tail_jsonl(scope_dirs[scope] / "order_lifecycle_events.jsonl", tail, scope=scope)
        for scope in RUNTIME_SCOPES
    }
    order_tail = {
        scope: _tail_jsonl(scope_dirs[scope] / "order_events.jsonl", tail, scope=scope)
        for scope in RUNTIME_SCOPES
    }
    fill_tail = {
        scope: _tail_jsonl(scope_dirs[scope] / "fill_events.jsonl", tail, scope=scope)
        for scope in RUNTIME_SCOPES
    }
    rank_tail = {
        scope: _tail_jsonl(scope_dirs[scope] / "rank_events.jsonl", tail, scope=scope)
        for scope in RUNTIME_SCOPES
    }
    strategy_score_tail = {
        scope: _tail_jsonl(
            scope_dirs[scope] / "strategy_score_events.jsonl",
            tail,
            scope=scope,
        )
        for scope in RUNTIME_SCOPES
    }
    event_stats = {scope: _store_stats(scope_dirs[scope]).__dict__ for scope in RUNTIME_SCOPES}
    lifecycle_stats = {
        scope: {
            "status_counts": _status_counts(
                scope_dirs[scope] / "order_lifecycle_events.jsonl",
                scope=scope,
            ),
            "top_reasons": _top_lifecycle_reasons(
                scope_dirs[scope] / "order_lifecycle_events.jsonl",
                5000,
                scope=scope,
            )[:10],
        }
        for scope in RUNTIME_SCOPES
    }
    risk_stats = {
        scope: _risk_stats(scope_dirs[scope], tail, scope=scope) for scope in RUNTIME_SCOPES
    }
    top_lifecycle_reject_reasons = {
        scope: _top_lifecycle_reasons(
            scope_dirs[scope] / "order_lifecycle_events.jsonl",
            tail,
            scope=scope,
            rejected_only=True,
        )
        for scope in RUNTIME_SCOPES
    }
    execution = _execution_observability(plan_cfg)
    enabled = _enabled_strategies(strategy_switch_approved, plan_cfg)
    enabled_strategies_by_symbol = {scope: enabled for scope in RUNTIME_SCOPES}
    audit_projection = load_audit_projection(
        runtime_id=runtime_id,
        scope=manifest_scope,
        artifacts_root=artifacts_root,
    )
    dashboard_projection = build_dashboard_projection(
        runtime_id=runtime_id,
        plan_cfg=plan_cfg,
        execution=execution,
        portfolio=portfolio_summaries,
        latest_portfolios=latest_portfolios,
        event_stats=event_stats,
        lifecycle_events={
            scope: _tail_jsonl(
                scope_dirs[scope] / "order_lifecycle_events.jsonl",
                5000,
                scope=scope,
            )
            for scope in RUNTIME_SCOPES
        },
        order_events={
            scope: _tail_jsonl(scope_dirs[scope] / "order_events.jsonl", 5000, scope=scope)
            for scope in RUNTIME_SCOPES
        },
        fill_events={
            scope: _tail_jsonl(scope_dirs[scope] / "fill_events.jsonl", 5000, scope=scope)
            for scope in RUNTIME_SCOPES
        },
        rank_events={
            scope: _tail_jsonl(scope_dirs[scope] / "rank_events.jsonl", 5000, scope=scope)
            for scope in RUNTIME_SCOPES
        },
        strategy_score_events={
            scope: _tail_jsonl(
                scope_dirs[scope] / "strategy_score_events.jsonl",
                5000,
                scope=scope,
            )
            for scope in RUNTIME_SCOPES
        },
        lifecycle_stats=lifecycle_stats,
        risk_stats=risk_stats,
        top_lifecycle_reject_reasons=top_lifecycle_reject_reasons,
        strategy_switch_proposal=strategy_switch_proposal,
        strategy_switch_approved=strategy_switch_approved,
        strategy_switch_rejected=strategy_switch_rejected,
        enabled_strategies_by_symbol=enabled_strategies_by_symbol,
        warning_codes=warnings,
        audit_projection=audit_projection,
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
            "path": str(manifest_path) if manifest_path is not None else None,
            "created_at": manifest.get("created_at"),
            "candidate_id": manifest.get("candidate_id"),
            "status": manifest.get("status"),
        },
        "event_stats": event_stats,
        "event_statuses": {
            scope: _jsonl_statuses(
                scope_dirs[scope] / "order_lifecycle_events.jsonl",
                scope=scope,
            )
            for scope in RUNTIME_SCOPES
        },
        "order_lifecycle_status_counts": {
            scope: _status_counts(
                scope_dirs[scope] / "order_lifecycle_events.jsonl",
                scope=scope,
            )
            for scope in RUNTIME_SCOPES
        },
        "pending_orders_count": {
            scope: _pending_orders_count(
                scope_dirs[scope] / "order_lifecycle_events.jsonl",
                scope=scope,
            )
            for scope in RUNTIME_SCOPES
        },
        "execution": execution,
        "portfolio": portfolio_summaries,
        "top_risk_reject_reasons": {
            scope: _top_risk_reject_reasons(
                scope_dirs[scope] / "order_lifecycle_events.jsonl",
                tail,
                scope=scope,
            )
            for scope in RUNTIME_SCOPES
        },
        "risk_stats": risk_stats,
        "active_symbols": {
            scope: _active_symbols_from_rank_events(
                scope_dirs[scope] / "rank_events.jsonl",
                scope=scope,
            )
            for scope in RUNTIME_SCOPES
        },
        "enabled_strategies_by_symbol": enabled_strategies_by_symbol,
        "top_lifecycle_reject_reasons": top_lifecycle_reject_reasons,
        "top_lifecycle_reasons": {
            scope: _top_lifecycle_reasons(
                scope_dirs[scope] / "order_lifecycle_events.jsonl",
                5000,
                scope=scope,
            )[:10]
            for scope in RUNTIME_SCOPES
        },
        "lifecycle_stats": lifecycle_stats,
        "event_tail": {
            scope: {"order_lifecycle_events": lifecycle_tail[scope]}
            for scope in RUNTIME_SCOPES
        },
        "plan": {
            "path": plan_meta.get("path"),
            "sha256": plan_meta.get("sha256"),
            "effective_config_summary": plan_cfg,
            "redaction_status": plan_meta.get("redaction_status"),
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
            "rejected": strategy_switch_rejected,
        },
        "warnings": main_warnings,
        "optional_warnings": optional_warnings,
        "dashboard_projection": dashboard_projection,
        "audit": audit_projection,
        "stores": {
            scope: {
                "dir": str(scope_dirs[scope]),
                "stats": _store_stats(scope_dirs[scope]).__dict__,
                "tail": {
                    "fill_events": fill_tail[scope],
                    "order_events": order_tail[scope],
                    "roll_events": _tail_jsonl(
                        scope_dirs[scope] / "roll_events.jsonl",
                        tail,
                        scope=scope,
                    ),
                    "rank_events": rank_tail[scope],
                    "strategy_score_events": strategy_score_tail[scope],
                    "order_lifecycle_events": lifecycle_tail[scope],
                },
            }
            for scope in RUNTIME_SCOPES
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
