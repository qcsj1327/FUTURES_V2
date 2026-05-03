from __future__ import annotations

from typing import Any

from web.readmodel.models import RunListItem, RunReadModel
from web.viewmodels.zh_mapping import (
    zh_position_side,
    zh_reason,
    zh_router_mode,
    zh_side,
)


def run_list_item_to_vm(item: RunListItem) -> dict[str, Any]:
    return {
        "runtime_id": item.runtime_id,
        "created_at": item.created_at,
        "approved": item.approved,
        "router_mode": item.router_mode,
        "router_mode_zh": zh_router_mode(item.router_mode),
        "universe_symbols": item.universe_symbols,
        "strategy_names": item.strategy_names,
        "plan_sha256": item.plan_sha256,
        "manifest_path": item.manifest_path,
    }


def run_to_vm(run: RunReadModel) -> dict[str, Any]:
    decision_payload = run.decision
    if not isinstance(decision_payload, dict):
        decision_payload = {}
    decision_raw = decision_payload.get("decision")
    decision_obj = decision_raw if isinstance(decision_raw, dict) else {}
    reasons_raw = decision_obj.get("reasons")
    reasons = reasons_raw if isinstance(reasons_raw, list) else []
    reasons_zh = [zh_reason(r if isinstance(r, str) else None) for r in reasons]

    router_raw = run.plan_config.get("router")
    router = router_raw if isinstance(router_raw, dict) else {}
    router_mode = router.get("mode") if isinstance(router.get("mode"), str) else None

    return {
        "runtime_id": run.runtime_id,
        "created_at": run.created_at,
        "candidate_id": run.candidate_id,
        "manifest_path": run.manifest_path,
        "plan": {
            "path": run.plan_path,
            "sha256": run.plan_sha256,
            "config": run.plan_config,
        },
        "router_mode": router_mode,
        "router_mode_zh": zh_router_mode(router_mode),
        "summaries": {
            "current": run.current_summary,
            "candidate": run.candidate_summary,
        },
        "decision": run.decision,
        "reasons_zh": reasons_zh,
        "approved": run.approved,
        "thresholds": run.thresholds,
        "warnings": run.warnings,
    }


def events_to_vm(payload: dict[str, Any]) -> dict[str, Any]:
    fill_raw = payload.get("fill_events")
    fill_events = fill_raw if isinstance(fill_raw, list) else []

    order_raw = payload.get("order_events")
    order_events = order_raw if isinstance(order_raw, list) else []

    rank_raw = payload.get("rank_events")
    rank_events = rank_raw if isinstance(rank_raw, list) else []

    tl_raw = payload.get("timeline")
    timeline = tl_raw if isinstance(tl_raw, list) else []

    def _annotate(ev: Any) -> Any:
        if not isinstance(ev, dict):
            return ev

        ev2 = dict(ev)

        r = ev.get("reason") if isinstance(ev.get("reason"), str) else None
        ev2["reason_zh"] = zh_reason(r)

        side = ev.get("side") if isinstance(ev.get("side"), str) else None
        ev2["side_zh"] = zh_side(side)

        ps = ev.get("position_side") if isinstance(ev.get("position_side"), str) else None
        ev2["position_side_zh"] = zh_position_side(ps)

        return ev2

    return {
        "runtime_id": payload.get("runtime_id"),
        "env": payload.get("env"),
        "tail": payload.get("tail"),
        "paths": payload.get("paths"),
        "fill_events": [_annotate(x) for x in fill_events],
        "order_events": [_annotate(x) for x in order_events],
        "rank_events": [_annotate(x) for x in rank_events],
        "timeline": [_annotate(x) for x in timeline],
    }
