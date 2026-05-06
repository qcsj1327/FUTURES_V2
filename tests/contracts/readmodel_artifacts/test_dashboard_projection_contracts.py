from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from domain.enums import PositionSide
from domain.state import PortfolioState, PositionKey, PositionState
from web.readmodel.dashboard_projection import build_dashboard_projection


def _plan(active_top_n: int = 1) -> dict[str, Any]:
    return {
        "runtime": {"mode": "live", "active_top_n": active_top_n},
        "universe": {"symbols": ["au"]},
        "instruments": {"roll_policy": {"contracts": {"au": "SHFE.au2406"}}},
    }


def _ts(value: str) -> int:
    return int(datetime.fromisoformat(value).replace(tzinfo=ZoneInfo("Asia/Shanghai")).timestamp())


def _projection(
    *,
    plan_cfg: dict[str, Any] | None = None,
    portfolio_obj: PortfolioState | None = None,
    lifecycle: list[dict[str, Any]] | None = None,
    orders: list[dict[str, Any]] | None = None,
    fills: list[dict[str, Any]] | None = None,
    rank: list[dict[str, Any]] | None = None,
    scores: list[dict[str, Any]] | None = None,
    proposal: dict[str, Any] | None = None,
    approved: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    effective_plan = plan_cfg or _plan()
    scope = effective_plan.get("runtime", {}).get("mode", "live")
    scoped: dict[str, list[dict[str, Any]]] = {
        "local": [],
        "dryrun": [],
        "live": [],
    }
    return build_dashboard_projection(
        runtime_id="rt_contract",
        plan_cfg=effective_plan,
        execution={"broker_type": "tqkq", "execution_mode": "live", "confirm_live": True},
        portfolio={
            "live": {
                "notional_by_symbol": {},
                "margin_by_symbol": {},
                "risk_ratio": 0.0,
                "margin_used": 0.0,
            },
            "local": None, "dryrun": None,
        },
        latest_portfolios={"live": portfolio_obj, "local": None, "dryrun": None},
        event_stats={
            "live": {"fill_events_lines": len(fills or [])} if scope == "live" else {},
            "local": {"fill_events_lines": len(fills or [])} if scope == "local" else {},
            "dryrun": {"fill_events_lines": len(fills or [])} if scope == "dryrun" else {},
        },
        lifecycle_events={**scoped, scope: _scoped_rows(lifecycle or [], scope, "order_lifecycle")},
        order_events={**scoped, scope: _scoped_rows(orders or [], scope, "order_event")},
        fill_events={**scoped, scope: _scoped_rows(fills or [], scope, "fill_event")},
        rank_events={**scoped, scope: _scoped_rows(rank or [], scope, "rank")},
        strategy_score_events={
            **scoped,
            scope: _scoped_rows(scores or [], scope, "strategy_score"),
        },
        lifecycle_stats={
            "local": {"status_counts": {}},
            "dryrun": {"status_counts": {}},
            "live": {"status_counts": {}},
        },
        risk_stats={"live": {}, "local": {}, "dryrun": {}},
        top_lifecycle_reject_reasons={"live": [], "local": [], "dryrun": []},
        strategy_switch_proposal=proposal,
        strategy_switch_approved=approved,
        strategy_switch_rejected=None,
        enabled_strategies_by_symbol={
            "local": {},
            "dryrun": {},
            "live": {"au": ["simple_strategy"]},
        },
        warning_codes=warnings or [],
    )


def _scoped_rows(rows: list[dict[str, Any]], scope: str, payload_type: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        item = dict(row)
        item.setdefault("runtime_profile", scope)
        item.setdefault("datastore_scope", scope)
        item.setdefault("event_id", f"{payload_type}-{idx}")
        item.setdefault("source", "contract")
        item.setdefault("payload_type", payload_type)
        out.append(item)
    return out


def _portfolio(qty: float = 1.0) -> PortfolioState:
    key = PositionKey("au", "SHFE.au2406", PositionSide.LONG)
    position = PositionState(
        instrument_id="au",
        trade_instrument_id="SHFE.au2406",
        position_side=PositionSide.LONG,
        quantity=qty,
        avg_price=450.0,
        unrealized_pnl=12.0,
        updated_ts=3,
    )
    return PortfolioState(runtime_id="rt_contract", positions={key: position}, updated_ts=3)


def test_pending_only_live_submit_does_not_create_position() -> None:
    projection = _projection(
        lifecycle=[
            {
                "order_id": "o1",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2406",
                "side": "buy",
                "position_side": "long",
                "quantity": 1.0,
                "status": "NEW",
                "reason": "new",
                "ts": 1,
            },
            {
                "order_id": "o1",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2406",
                "side": "buy",
                "position_side": "long",
                "quantity": 1.0,
                "status": "SUBMITTED",
                "reason": "order_submitted",
                "ts": 2,
            },
        ],
        warnings=["missing_candidate_summary", "missing_decision"],
    )

    assert projection["positions"]["live"]["items"] == []
    pending = projection["pending_orders"]["live"]
    assert pending["count"] == 1
    assert pending["items"][0]["status"] == "SUBMITTED"
    assert projection["order_status"]["live"]["counts"] == {"SUBMITTED": 1}
    assert {x["code"] for x in projection["alerts"]["items"]}.isdisjoint(
        {"missing_candidate_summary", "missing_decision"}
    )
    assert {x["code"] for x in projection["alerts"]["optional_warnings"]} == {
        "missing_candidate_summary",
        "missing_decision",
    }


def test_partial_fill_splits_position_and_remaining_pending() -> None:
    projection = _projection(
        portfolio_obj=_portfolio(qty=0.4),
        lifecycle=[
            {
                "order_id": "o1",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2406",
                "side": "buy",
                "position_side": "long",
                "quantity": 1.0,
                "filled_quantity": 0.4,
                "remaining_quantity": 0.6,
                "status": "PARTIAL",
                "reason": "partial_fill",
                "ts": 3,
            }
        ],
    )

    positions = projection["positions"]["live"]["items"]
    pending = projection["pending_orders"]["live"]["items"]
    assert positions[0]["quantity"] == 0.4
    assert positions[0]["source"] == "portfolio_snapshot"
    assert pending[0]["filled_quantity"] == 0.4
    assert pending[0]["remaining_quantity"] == 0.6


def test_pending_order_projects_unrealized_pnl_for_filled_quantity_only() -> None:
    projection = _projection(
        lifecycle=[
            {
                "order_id": "o1",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2406",
                "side": "buy",
                "position_side": "long",
                "quantity": 2.0,
                "filled_quantity": 0.5,
                "remaining_quantity": 1.5,
                "avg_fill_price": 450.0,
                "market_price": 460.0,
                "status": "PARTIAL",
                "reason": "partial_fill",
                "ts": 3,
            }
        ],
    )

    pending = projection["pending_orders"]["live"]["items"][0]
    assert pending["unrealized_pnl"] == 5.0
    assert pending["latest_market_price"] == 460.0
    assert pending["avg_fill_price"] == 450.0


def test_quote_mapping_prefers_real_trade_contract_over_main_alias() -> None:
    projection = _projection(
        plan_cfg={
            "runtime": {"mode": "live", "active_top_n": 1},
            "universe": {"symbols": ["au"]},
            "instruments": {"roll_policy": {"contracts": {"au": "au_main"}}},
        },
        orders=[
            {
                "order_id": "o1",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2406",
                "market_price": 450.0,
                "ts": 1,
            }
        ],
    )

    quote = projection["quotes"]["live"]["by_symbol"]["au"]
    assert quote["trade_instrument_id"] == "SHFE.au2406"
    assert "SHFE.au2406" in projection["quotes"]["live"]["by_contract"]


def test_quote_mapping_resolves_fixed_main_schedule_by_latest_tick() -> None:
    projection = _projection(
        plan_cfg={
            "runtime": {"mode": "local", "active_top_n": 1},
            "universe": {"symbols": ["au"]},
            "instruments": {
                "roll_policy": {
                    "mode": "fixed_main",
                    "contracts": {"au": "au_main"},
                    "main_contract_schedule": {"au": ["au2506", "au2507"]},
                }
            },
        },
        orders=[{"order_id": "o1", "symbol": "au", "market_price": 450.0, "ts": 3}],
    )

    assert projection["quotes"]["local"]["by_symbol"]["au"]["trade_instrument_id"] == "au2507"


def test_quote_mapping_separates_market_and_execution_prices() -> None:
    projection = _projection(
        orders=[
            {
                "order_id": "o1",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2406",
                "price": 449.0,
                "stop_loss": 440.0,
                "take_profit": 470.0,
                "market_price": 450.0,
                "ts": 1,
            }
        ],
        fills=[
            {
                "order_id": "o1",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2406",
                "fill_price": 451.0,
                "avg_fill_price": 451.0,
                "ts": 2,
            }
        ],
    )

    quote = projection["quotes"]["live"]["by_symbol"]["au"]
    assert quote["trade_instrument_id"] == "SHFE.au2406"
    assert quote["latest_market_price"] == 450.0
    assert quote["last_execution_price"] == 451.0
    assert quote["order_price"] == 449.0
    assert quote["stop_loss"] == 440.0
    assert quote["take_profit"] == 470.0
    assert projection["quotes"]["live"]["by_contract"]["SHFE.au2406"] is quote

    missing = _projection()["quotes"]["live"]["by_symbol"]["au"]
    assert missing["available"] is False
    assert missing["reason"] == "quote_not_recorded"


def test_quote_tradability_uses_trading_sessions_not_market_price_presence() -> None:
    projection = _projection(
        plan_cfg={
            "runtime": {"mode": "dryrun", "active_top_n": 1},
            "universe": {"symbols": ["au"]},
            "instruments": {
                "trading_sessions": {
                    "au": [
                        {"start": "09:00", "end": "15:00"},
                        {"start": "21:00", "end": "02:30"},
                    ]
                },
                "roll_policy": {"contracts": {"au": "SHFE.au2406"}},
            },
        },
        orders=[
            {
                "order_id": "o1",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2406",
                "market_price": 450.0,
                "ts": _ts("2026-05-05T03:00:00"),
            }
        ],
    )

    quote = projection["quotes"]["dryrun"]["by_symbol"]["au"]
    assert quote["available"] is True
    assert quote["tradability"] == {
        "state": "non_trading_time",
        "reason": "non_trading_time",
        "source": "trading_sessions",
        "next_action": "等待交易时段",
    }


def test_quote_tradability_uses_market_ts_not_runtime_tick() -> None:
    projection = _projection(
        plan_cfg={
            "runtime": {"mode": "dryrun", "active_top_n": 1},
            "universe": {"symbols": ["au"]},
            "instruments": {
                "trading_sessions": {
                    "au": [
                        {"start": "09:00", "end": "10:15"},
                        {"start": "21:00", "end": "02:30"},
                    ]
                },
                "roll_policy": {"contracts": {"au": "SHFE.au2406"}},
            },
        },
        orders=[
            {
                "order_id": "o1",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2406",
                "market_price": 450.0,
                "ts": 75,
                "market_ts": _ts("2026-05-08T21:13:00"),
            }
        ],
    )

    quote = projection["quotes"]["dryrun"]["by_symbol"]["au"]
    assert quote["tradability"] == {
        "state": "tradable",
        "reason": "market_quote_available",
        "source": "market_quote",
        "next_action": "等待价格触发",
    }


def test_local_quote_tradability_ignores_real_exchange_sessions() -> None:
    projection = _projection(
        plan_cfg={
            "runtime": {"mode": "local", "active_top_n": 1},
            "universe": {"symbols": ["au"]},
            "instruments": {
                "trading_sessions": {
                    "au": [
                        {"start": "09:00", "end": "15:00"},
                        {"start": "21:00", "end": "02:30"},
                    ]
                },
                "roll_policy": {"contracts": {"au": "SHFE.au2406"}},
            },
        },
        orders=[
            {
                "order_id": "o1",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2406",
                "market_price": 450.0,
                "ts": _ts("2026-05-05T03:00:00"),
            }
        ],
    )

    quote = projection["quotes"]["local"]["by_symbol"]["au"]
    assert quote["available"] is True
    assert quote["tradability"] == {
        "state": "tradable",
        "reason": "local_simulated_quote_available",
        "source": "local_simulated_quote",
        "next_action": "等待价格触发",
    }


def test_active_symbols_falls_back_to_strategy_switch_proposal() -> None:
    projection = _projection(
        rank=[],
        proposal={"active_top_n_symbols": ["au"]},
    )

    active = projection["active_symbols"]["live"]
    assert active["symbols"] == ["au"]
    assert active["source"] == "strategy_switch_proposal"


def test_strategy_scores_are_projected_from_latest_score_events() -> None:
    projection = _projection(
        scores=[
            {
                "ts": 1,
                "symbol": "au",
                "strategy_name": "simple_strategy",
                "strategy_id": "simple_strategy",
                "final_score": 3.9,
                "raw_score": 4.0,
                "cost_penalty": 0.1,
                "risk_penalty": 0.0,
                "scoring_model": "cost_risk_v2",
            }
        ],
    )

    scores = projection["strategy_scores"]["live"]["latest_by_symbol"]["au"]
    assert scores[0]["strategy_id"] == "simple_strategy"
    assert scores[0]["final_score"] == 3.9
    assert scores[0]["raw_score"] == 4.0


def test_strategy_switch_projection_uses_auto_promotion_state_model() -> None:
    projection = _projection(
        plan_cfg={
            "runtime": {"mode": "live", "active_top_n": 0},
            "universe": {"symbols": ["au"]},
            "strategies": [{"name": "simple_strategy", "symbols": ["au"]}],
            "strategy_switch": {
                "enabled_by_symbol": {"au": ["simple_strategy"]},
                "approval_required": False,
            },
        },
        proposal={
            "thresholds": {"approval_required": False},
            "enabled_strategies_by_symbol": {"au": ["volume_trend_filter"]},
            "current_enabled_by_symbol": {"au": ["simple_strategy"]},
        },
        approved={"enabled_strategies_by_symbol": {"au": ["volume_trend_filter"]}},
    )

    sw = projection["strategy_switch"]
    assert sw["state"] == "approved"
    assert sw["approval_required"] is False
    assert sw["enabled_strategies_by_symbol"] == {"au": ["volume_trend_filter"]}


def test_strategy_switch_projection_reports_rejected_artifact() -> None:
    projection = build_dashboard_projection(
        runtime_id="rt_contract",
        plan_cfg={
            "runtime": {"mode": "live", "active_top_n": 3},
            "universe": {"symbols": ["au"]},
            "strategies": [{"name": "simple_strategy", "symbols": ["au"]}],
            "strategy_switch": {
                "enabled_by_symbol": {"au": ["simple_strategy"]},
                "approval_required": True,
            },
        },
        execution={},
        portfolio={"live": {}, "local": None, "dryrun": None},
        latest_portfolios={"live": None, "local": None, "dryrun": None},
        event_stats={"live": {}, "local": {}, "dryrun": {}},
        lifecycle_events={"live": [], "local": [], "dryrun": []},
        order_events={"live": [], "local": [], "dryrun": []},
        fill_events={"live": [], "local": [], "dryrun": []},
        rank_events={"live": [], "local": [], "dryrun": []},
        strategy_score_events={"live": [], "local": [], "dryrun": []},
        lifecycle_stats={
            "local": {"status_counts": {}},
            "dryrun": {"status_counts": {}},
            "live": {"status_counts": {}},
        },
        risk_stats={"live": {}, "local": {}, "dryrun": {}},
        top_lifecycle_reject_reasons={"live": [], "local": [], "dryrun": []},
        strategy_switch_proposal={"thresholds": {"approval_required": True}},
        strategy_switch_approved=None,
        strategy_switch_rejected={"kind": "strategy_switch_rejected"},
        enabled_strategies_by_symbol={"live": {"au": ["simple_strategy"]}},
        warning_codes=[],
    )

    assert projection["strategy_switch"]["state"] == "rejected"
    assert projection["strategy_switch"]["approval_required"] is True


def test_existing_account_position_and_current_pending_order_coexist() -> None:
    projection = _projection(
        portfolio_obj=_portfolio(qty=2.0),
        lifecycle=[
            {
                "order_id": "o2",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2406",
                "side": "buy",
                "position_side": "long",
                "quantity": 1.0,
                "status": "SUBMITTED",
                "reason": "order_submitted",
                "ts": 10,
            }
        ],
        fills=[],
    )

    assert projection["positions"]["live"]["items"][0]["quantity"] == 2.0
    assert projection["pending_orders"]["live"]["items"][0]["quantity"] == 1.0


def _function_body(source: str, name: str) -> str:
    start = source.index(f"function {name}")
    next_start = source.find("\nfunction ", start + 1)
    return source[start : next_start if next_start != -1 else len(source)]


def test_ui_core_dashboard_sections_consume_projection_contract() -> None:
    source = Path("web/ui/app.js").read_text(encoding="utf-8")

    assert 'projectionItems("positions")' in _function_body(source, "positionsTable")
    assert 'projectionItems("pending_orders")' in _function_body(source, "pendingOrdersTable")
    assert "item.unrealized_pnl" in _function_body(source, "pendingOrdersTable")
    assert "orderUnrealizedPnl(x)" in _function_body(source, "lifecycleTable")
    assert "projection()?.alerts?.items" in _function_body(source, "alertsList")
    assert 'projectionScope("active_symbols")' in _function_body(
        source,
        "activeSymbolsForDisplay",
    )

    assert "liveTails()" not in source
    assert "projectionLive(" not in source
    assert "state.dashboard.warnings" not in _function_body(source, "alertsList")
    assert "currentTails().order_events" not in _function_body(source, "candidateRows")
    assert "currentTails().order_lifecycle_events" not in _function_body(source, "candidateRows")
    assert "source=dashboard_projection" not in source
    assert "投影" not in source
    assert "触发价" not in _function_body(source, "gatesTable")
    assert 'projectionScope("order_status").counts' in _function_body(source, "renderHome")
    assert "quote?.stop_loss" in _function_body(source, "candidateRows")
    assert "quote?.take_profit" in _function_body(source, "candidateRows")
    assert "data-approve-switch" not in _function_body(source, "switchApprovalPanel")
    assert "data-reject-switch" not in _function_body(source, "switchApprovalPanel")
