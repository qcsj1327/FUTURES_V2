from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from adapters.storage.datastore_fs import JSONLFileDataStore
from config.models import RunPlan, StrategySpec


def strategy_switch_dir(artifacts_root: Path) -> Path:
    return artifacts_root / "strategy_switch"


def proposal_path(*, runtime_id: str, artifacts_root: Path) -> Path:
    return strategy_switch_dir(artifacts_root) / f"strategy_switch_proposal_{runtime_id}.json"


def approved_path(*, runtime_id: str, artifacts_root: Path) -> Path:
    return strategy_switch_dir(artifacts_root) / f"strategy_switch_approved_{runtime_id}.json"


def load_approved_strategy_map(
    *,
    runtime_id: str,
    artifacts_root: Path,
) -> dict[str, list[str]] | None:
    path = approved_path(runtime_id=runtime_id, artifacts_root=artifacts_root)
    if not path.exists():
        return None
    payload = _read_json(path)
    if payload.get("kind") != "strategy_switch_approved":
        raise ValueError(f"invalid strategy switch approved artifact: {path}")
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
    env: str,
    store: JSONLFileDataStore,
    artifacts_root: Path,
    universe_symbols: list[str],
    active_top_n: int,
    min_score: float = 1.0,
) -> Path:
    scores = store.read_strategy_score_events(env=env)
    ranks = store.read_rank_events(env=env)
    active_symbols = _active_symbols_from_rank_events(ranks, universe_symbols, active_top_n)
    by_symbol = _rank_strategies(scores, universe_symbols)
    symbols_payload: dict[str, dict[str, Any]] = {}
    enabled_by_symbol: dict[str, list[str]] = {}

    for sym in sorted(universe_symbols):
        ranked = by_symbol.get(sym, [])
        recommended = [x["strategy_name"] for x in ranked[:1] if float(x["score"]) >= min_score]
        if not recommended and ranked:
            recommended = [ranked[0]["strategy_name"]]
        if recommended:
            enabled_by_symbol[sym] = recommended
        symbols_payload[sym] = {
            "active": sym in active_symbols,
            "ranked_strategies": ranked,
            "recommended_enabled_strategies": recommended,
            "reason": "highest_strategy_score",
        }

    payload = {
        "kind": "strategy_switch_proposal",
        "runtime_id": runtime_id,
        "env": env,
        "created_at": datetime.now(UTC).isoformat(),
        "active_top_n_symbols": sorted(active_symbols),
        "thresholds": {
            "min_score": min_score,
            "max_enabled_strategies_per_symbol": 1,
        },
        "symbols": symbols_payload,
        "enabled_strategies_by_symbol": enabled_by_symbol,
    }
    path = proposal_path(runtime_id=runtime_id, artifacts_root=artifacts_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_strategy_switch_approved(*, proposal: dict[str, Any], output_path: Path) -> Path:
    enabled = proposal.get("enabled_strategies_by_symbol")
    if not isinstance(enabled, dict):
        raise ValueError("proposal missing enabled_strategies_by_symbol")
    runtime_id = proposal.get("runtime_id")
    if not isinstance(runtime_id, str) or not runtime_id:
        raise ValueError("proposal missing runtime_id")
    payload = {
        "kind": "strategy_switch_approved",
        "runtime_id": runtime_id,
        "approved_at": datetime.now(UTC).isoformat(),
        "source_proposal": str(proposal.get("path", "")),
        "active_top_n_symbols": proposal.get("active_top_n_symbols", []),
        "thresholds": proposal.get("thresholds", {}),
        "enabled_strategies_by_symbol": enabled,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected json object: {path}")
    return payload


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
                "score": float(event.get("score", 0.0)),
                "decision": event.get("decision"),
                "strength": event.get("strength"),
                "confidence": float(event.get("confidence", 0.0)),
            }
        )
    for symbol, items in grouped.items():
        grouped[symbol] = sorted(items, key=lambda x: (-float(x["score"]), x["strategy_name"]))
    return grouped
