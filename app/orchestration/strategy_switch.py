from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adapters.storage.datastore_fs import JSONLFileDataStore
from config.models import RunPlan, StrategySpec


def strategy_switch_dir(artifacts_root: Path, *, scope: str | None = None) -> Path:
    if not scope:
        raise ValueError("strategy_switch artifacts require explicit scope")
    return artifacts_root / scope / "strategy_switch"


def proposal_path(*, runtime_id: str, artifacts_root: Path, scope: str | None = None) -> Path:
    return (
        strategy_switch_dir(artifacts_root, scope=scope)
        / f"strategy_switch_proposal_{runtime_id}.json"
    )


def approved_path(*, runtime_id: str, artifacts_root: Path, scope: str | None = None) -> Path:
    return (
        strategy_switch_dir(artifacts_root, scope=scope)
        / f"strategy_switch_approved_{runtime_id}.json"
    )


def rejected_path(*, runtime_id: str, artifacts_root: Path, scope: str | None = None) -> Path:
    return (
        strategy_switch_dir(artifacts_root, scope=scope)
        / f"strategy_switch_rejected_{runtime_id}.json"
    )


def load_approved_strategy_map(
    *,
    runtime_id: str,
    artifacts_root: Path,
    expected_runtime_profile: str,
    expected_datastore_scope: str,
    diagnostics: list[str] | None = None,
) -> dict[str, list[str]] | None:
    path = approved_path(
        runtime_id=runtime_id,
        artifacts_root=artifacts_root,
        scope=expected_datastore_scope,
    )
    if not path.exists():
        _record_diagnostic(
            diagnostics,
            f"strategy_switch_approved_not_found:{expected_datastore_scope}:{runtime_id}",
        )
        return None
    return _load_approved_strategy_map_from_path(
        path=path,
        runtime_id=runtime_id,
        expected_runtime_profile=expected_runtime_profile,
        expected_datastore_scope=expected_datastore_scope,
        diagnostics=diagnostics,
    )


def _load_approved_strategy_map_from_path(
    *,
    path: Path,
    runtime_id: str,
    expected_runtime_profile: str,
    expected_datastore_scope: str,
    diagnostics: list[str] | None,
) -> dict[str, list[str]] | None:
    payload = _read_json(path)
    if payload.get("kind") != "strategy_switch_approved":
        raise ValueError(f"invalid strategy switch approved artifact: {path}")
    if payload.get("runtime_id") != runtime_id:
        _record_diagnostic(diagnostics, f"strategy_switch_runtime_id_mismatch:{path}")
        return None
    runtime_profile = payload.get("runtime_profile")
    datastore_scope = payload.get("datastore_scope")
    is_live = payload.get("is_live")
    expected_is_live = expected_datastore_scope == "live"
    if runtime_profile != expected_runtime_profile:
        _record_diagnostic(diagnostics, f"strategy_switch_runtime_profile_mismatch:{path}")
        return None
    if datastore_scope != expected_datastore_scope:
        _record_diagnostic(diagnostics, f"strategy_switch_datastore_scope_mismatch:{path}")
        return None
    if is_live is not expected_is_live:
        _record_diagnostic(diagnostics, f"strategy_switch_is_live_mismatch:{path}")
        return None
    raw = payload.get("enabled_strategies_by_symbol")
    if not isinstance(raw, dict):
        raise ValueError("strategy switch approved missing enabled_strategies_by_symbol")
    out: dict[str, list[str]] = {}
    for sym, names in raw.items():
        if not isinstance(sym, str) or not isinstance(names, list):
            raise ValueError("invalid enabled_strategies_by_symbol schema")
        parsed = [x for x in names if isinstance(x, str) and x]
        if parsed:
            out[sym] = parsed
    return out


def apply_approved_strategy_switch(plan: RunPlan) -> RunPlan:
    enabled = load_approved_strategy_map(
        runtime_id=plan.runtime.runtime_id,
        artifacts_root=plan.datastore.artifacts_root,
        expected_runtime_profile=plan.runtime.mode,
        expected_datastore_scope=plan.runtime.mode,
    )
    if enabled is None:
        return plan

    filtered: list[StrategySpec] = []
    for strategy in plan.strategies:
        symbols = [
            sym
            for sym in strategy.symbols
            if strategy.name in enabled.get(sym, [])
        ]
        if symbols:
            filtered.append(replace(strategy, symbols=symbols))
    if not filtered:
        raise ValueError("strategy switch approved artifact disables all strategies")
    return replace(plan, strategies=filtered)


def write_strategy_switch_proposal(
    *,
    runtime_id: str,
    scope: str,
    store: JSONLFileDataStore,
    artifacts_root: Path,
    universe_symbols: list[str],
    active_top_n: int,
    current_enabled_by_symbol: dict[str, list[str]] | None = None,
    approval_required: bool = True,
    min_score: float = 1.0,
    max_enabled_strategies_per_symbol: int = 1,
) -> Path:
    scores = store.read_strategy_score_events(scope=scope)
    ranks = store.read_rank_events(scope=scope)
    active_symbols = _active_symbols_from_rank_events(ranks, universe_symbols, active_top_n)
    by_symbol = _rank_strategies(scores, universe_symbols)
    symbols_payload: dict[str, dict[str, Any]] = {}
    enabled_by_symbol: dict[str, list[str]] = {}
    current_enabled = {
        sym: sorted(set(names))
        for sym, names in (current_enabled_by_symbol or {}).items()
    }

    for sym in sorted(universe_symbols):
        ranked = by_symbol.get(sym, [])
        recommended = [
            x["strategy_name"]
            for x in ranked[:max_enabled_strategies_per_symbol]
            if float(x["score"]) >= min_score
        ]
        if not recommended and ranked:
            recommended = [ranked[0]["strategy_name"]]
        if recommended:
            enabled_by_symbol[sym] = recommended
        current = current_enabled.get(sym, [])
        symbols_payload[sym] = {
            "active": sym in active_symbols,
            "ranked_strategies": ranked,
            "current_enabled_strategies": current,
            "recommended_enabled_strategies": recommended,
            "switch_required": bool(recommended and recommended != current),
            "reason": "highest_final_score_cost_risk_adjusted",
        }

    payload = {
        "kind": "strategy_switch_proposal",
        "schema_version": 1,
        "runtime_id": runtime_id,
        "runtime_profile": scope,
        "datastore_scope": scope,
        "is_live": scope == "live",
        "created_at": datetime.now(UTC).isoformat(),
        "active_top_n_symbols": sorted(active_symbols),
        "thresholds": {
            "min_score": min_score,
            "max_enabled_strategies_per_symbol": max_enabled_strategies_per_symbol,
            "scoring_model": "cost_risk_v2",
            "approval_required": approval_required,
        },
        "symbols": symbols_payload,
        "current_enabled_by_symbol": current_enabled,
        "enabled_strategies_by_symbol": enabled_by_symbol,
    }
    path = proposal_path(runtime_id=runtime_id, artifacts_root=artifacts_root, scope=scope)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_strategy_switch_auto_approved(*, proposal_path: Path) -> Path:
    proposal = _read_json(proposal_path)
    runtime_id = proposal.get("runtime_id")
    if not isinstance(runtime_id, str) or not runtime_id:
        raise ValueError("proposal missing runtime_id")
    proposal["path"] = str(proposal_path)
    return write_strategy_switch_approved(
        proposal=proposal,
        output_path=proposal_path.with_name(f"strategy_switch_approved_{runtime_id}.json"),
    )


def write_strategy_switch_approved(*, proposal: dict[str, Any], output_path: Path) -> Path:
    enabled = proposal.get("enabled_strategies_by_symbol")
    if not isinstance(enabled, dict):
        raise ValueError("proposal missing enabled_strategies_by_symbol")
    runtime_id = proposal.get("runtime_id")
    if not isinstance(runtime_id, str) or not runtime_id:
        raise ValueError("proposal missing runtime_id")
    runtime_profile = proposal.get("runtime_profile")
    datastore_scope = proposal.get("datastore_scope")
    if not isinstance(runtime_profile, str) or not runtime_profile:
        raise ValueError("proposal missing runtime_profile")
    if not isinstance(datastore_scope, str) or not datastore_scope:
        raise ValueError("proposal missing datastore_scope")
    payload = {
        "kind": "strategy_switch_approved",
        "schema_version": 1,
        "runtime_id": runtime_id,
        "runtime_profile": runtime_profile,
        "datastore_scope": datastore_scope,
        "is_live": datastore_scope == "live",
        "generated_at": datetime.now(UTC).isoformat(),
        "promotion_mode": "automatic",
        "approved_at": datetime.now(UTC).isoformat(),
        "source_proposal": str(proposal.get("path", "")),
        "active_top_n_symbols": proposal.get("active_top_n_symbols", []),
        "thresholds": proposal.get("thresholds", {}),
        "enabled_strategies_by_symbol": enabled,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def write_strategy_switch_rejected(*, proposal: dict[str, Any], output_path: Path) -> Path:
    runtime_id = proposal.get("runtime_id")
    if not isinstance(runtime_id, str) or not runtime_id:
        raise ValueError("proposal missing runtime_id")
    payload = {
        "kind": "strategy_switch_rejected",
        "schema_version": 1,
        "runtime_id": runtime_id,
        "runtime_profile": proposal.get("runtime_profile"),
        "datastore_scope": proposal.get("datastore_scope"),
        "is_live": proposal.get("datastore_scope") == "live",
        "rejected_at": datetime.now(UTC).isoformat(),
        "source_proposal": str(proposal.get("path", "")),
        "active_top_n_symbols": proposal.get("active_top_n_symbols", []),
        "thresholds": proposal.get("thresholds", {}),
        "current_enabled_by_symbol": proposal.get("current_enabled_by_symbol", {}),
        "rejected_enabled_strategies_by_symbol": proposal.get(
            "enabled_strategies_by_symbol", {}
        ),
        "reason": "manual_reject",
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected json object: {path}")
    return payload


def _record_diagnostic(diagnostics: list[str] | None, reason: str) -> None:
    if diagnostics is not None:
        diagnostics.append(reason)


def _active_symbols_from_rank_events(
    events: list[dict[str, Any]],
    universe_symbols: list[str],
    active_top_n: int,
) -> set[str]:
    if active_top_n <= 0 or not events:
        return set(universe_symbols)
    last = events[-1]
    scores = last.get("scores")
    if not isinstance(scores, list):
        return set(universe_symbols)
    out: set[str] = set()
    for item in scores:
        if isinstance(item, dict) and isinstance(item.get("symbol"), str):
            out.add(item["symbol"])
    return out or set(universe_symbols)


def _rank_strategies(
    events: list[dict[str, Any]],
    universe_symbols: list[str],
) -> dict[str, list[dict[str, Any]]]:
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for event in events:
        symbol = event.get("symbol")
        strategy = event.get("strategy_name")
        if not isinstance(symbol, str) or not isinstance(strategy, str):
            continue
        latest[(symbol, strategy)] = event

    grouped: dict[str, list[dict[str, Any]]] = {sym: [] for sym in universe_symbols}
    for (symbol, strategy), event in latest.items():
        grouped.setdefault(symbol, []).append(
            {
                "strategy_name": strategy,
                "score": float(event.get("final_score", event.get("score", 0.0))),
                "raw_score": float(event.get("raw_score", event.get("score", 0.0))),
                "cost_penalty": float(event.get("cost_penalty", 0.0)),
                "risk_penalty": float(event.get("risk_penalty", 0.0)),
                "final_score": float(event.get("final_score", event.get("score", 0.0))),
                "decision": event.get("decision"),
                "strength": event.get("strength"),
                "confidence": float(event.get("confidence", 0.0)),
            }
        )
    for symbol, items in grouped.items():
        grouped[symbol] = sorted(items, key=lambda x: (-float(x["score"]), x["strategy_name"]))
    return grouped
