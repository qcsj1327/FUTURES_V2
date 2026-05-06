from __future__ import annotations

from typing import Any

from web.readmodel.dashboard_projection import build_dashboard_projection


def _plan(scope: str = "live") -> dict[str, Any]:
    return {
        "runtime": {"mode": scope, "active_top_n": 1},
        "universe": {"symbols": ["au"]},
        "instruments": {"roll_policy": {"contracts": {"au": "SHFE.au2406"}}},
    }


def _projection(
    *,
    scope: str = "live",
    lifecycle_events: dict[str, list[dict[str, Any]]] | None = None,
    order_events: dict[str, list[dict[str, Any]]] | None = None,
    fill_events: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    empty: dict[str, list[dict[str, Any]]] = {"local": [], "dryrun": [], "live": []}
    return build_dashboard_projection(
        runtime_id="rt_projection_scope",
        plan_cfg=_plan(scope),
        execution={},
        portfolio={"local": None, "dryrun": None, "live": {}},
        latest_portfolios={"local": None, "dryrun": None, "live": None},
        event_stats={"local": {}, "dryrun": {}, "live": {}},
        lifecycle_events=lifecycle_events or empty,
        order_events=order_events or empty,
        fill_events=fill_events or empty,
        rank_events=empty,
        strategy_score_events=empty,
        lifecycle_stats={"local": {}, "dryrun": {}, "live": {}},
        risk_stats={"local": {}, "dryrun": {}, "live": {}},
        top_lifecycle_reject_reasons={"local": [], "dryrun": [], "live": []},
        strategy_switch_proposal=None,
        strategy_switch_approved=None,
        strategy_switch_rejected=None,
        enabled_strategies_by_symbol={"local": {}, "dryrun": {}, "live": {}},
        warning_codes=[],
    )


def _event(scope: str, event_id: str, *, payload_type: str = "order_event") -> dict[str, Any]:
    return {
        "event_id": event_id,
        "runtime_profile": scope,
        "datastore_scope": scope,
        "source": "runtime",
        "payload_type": payload_type,
        "order_id": event_id,
        "symbol": "au",
        "trade_instrument_id": "SHFE.au2406",
        "market_price": 450.0,
        "status": "SUBMITTED",
        "quantity": 1.0,
        "ts": 1,
    }


def test_projection_output_preserves_scope_source_and_event_id() -> None:
    event = _event("live", "evt-live-1", payload_type="order_lifecycle")
    projection = _projection(lifecycle_events={"local": [], "dryrun": [], "live": [event]})

    pending = projection["pending_orders"]["live"]
    assert pending["runtime_profile"] == "live"
    assert pending["datastore_scope"] == "live"
    assert pending["source_event_ids"] == ["evt-live-1"]
    assert pending["event_sources"] == ["runtime"]
    assert pending["items"][0]["source_event_id"] == "evt-live-1"


def test_dryrun_and_local_events_are_not_projected_as_live_facts() -> None:
    dryrun_event = _event("dryrun", "evt-dryrun")
    local_event = _event("local", "evt-local")
    projection = _projection(
        order_events={"local": [], "dryrun": [], "live": [dryrun_event, local_event]},
        fill_events={"local": [], "dryrun": [], "live": [dryrun_event, local_event]},
    )

    live_quotes = projection["quotes"]["live"]
    assert "evt-dryrun" not in live_quotes["source_event_ids"]
    assert "evt-local" not in live_quotes["source_event_ids"]
    assert live_quotes["by_symbol"]["au"]["available"] is False
    assert projection["positions"]["live"]["items"] == []


def test_scopes_remain_separate_by_default() -> None:
    local_event = _event("local", "evt-local")
    dryrun_event = _event("dryrun", "evt-dryrun")
    live_event = _event("live", "evt-live")
    projection = _projection(
        order_events={
            "local": [local_event],
            "dryrun": [dryrun_event],
            "live": [live_event],
        }
    )

    assert projection["quotes"]["local"]["source_event_ids"] == ["evt-local"]
    assert projection["quotes"]["dryrun"]["source_event_ids"] == ["evt-dryrun"]
    assert projection["quotes"]["live"]["source_event_ids"] == ["evt-live"]


def test_legacy_flat_row_missing_envelope_is_not_projected_as_live_truth() -> None:
    legacy_row = {
        "order_id": "legacy-1",
        "symbol": "au",
        "trade_instrument_id": "SHFE.au2406",
        "status": "SUBMITTED",
        "quantity": 1.0,
        "market_price": 450.0,
        "ts": 1,
    }
    projection = _projection(
        lifecycle_events={"local": [], "dryrun": [], "live": [legacy_row]},
        order_events={"local": [], "dryrun": [], "live": [legacy_row]},
    )

    assert projection["pending_orders"]["live"]["source_scope_unknown"] is False
    assert projection["pending_orders"]["live"]["source_scope_unknown_count"] == 0
    assert projection["pending_orders"]["live"]["items"] == []
    assert projection["quotes"]["live"]["by_symbol"]["au"]["available"] is False
    assert projection["positions"]["live"]["items"] == []
