from __future__ import annotations

from pathlib import Path

from domain.enums import PositionSide
from domain.state import PortfolioState, PositionKey, PositionState
from tools.dashboard_projection import build_dashboard_projection


def _plan(active_top_n: int = 1) -> dict:
    return {
        "runtime": {"mode": "tqkq_live", "active_top_n": active_top_n},
        "universe": {"symbols": ["au"]},
        "instruments": {"roll_policy": {"contracts": {"au": "SHFE.au2406"}}},
    }


def _projection(
    *,
    plan_cfg: dict | None = None,
    portfolio_obj: PortfolioState | None = None,
    lifecycle: list[dict] | None = None,
    orders: list[dict] | None = None,
    fills: list[dict] | None = None,
    rank: list[dict] | None = None,
    proposal: dict | None = None,
    warnings: list[str] | None = None,
) -> dict:
    return build_dashboard_projection(
        runtime_id="rt_contract",
        plan_cfg=plan_cfg or _plan(),
        execution={"broker_type": "tqkq_live", "execution_mode": "live", "confirm_live": True},
        portfolio={
            "live": {
                "notional_by_symbol": {},
                "margin_by_symbol": {},
                "risk_ratio": 0.0,
                "margin_used": 0.0,
            },
            "sandbox": None,
        },
        latest_portfolios={"live": portfolio_obj, "sandbox": None},
        event_stats={"live": {"fill_events_lines": len(fills or [])}, "sandbox": {}},
        lifecycle_events={"live": lifecycle or [], "sandbox": []},
        order_events={"live": orders or [], "sandbox": []},
        fill_events={"live": fills or [], "sandbox": []},
        rank_events={"live": rank or [], "sandbox": []},
        lifecycle_stats={"live": {"status_counts": {}}, "sandbox": {"status_counts": {}}},
        risk_stats={"live": {}, "sandbox": {}},
        top_lifecycle_reject_reasons={"live": [], "sandbox": []},
        strategy_switch_proposal=proposal,
        strategy_switch_approved=None,
        enabled_strategies_by_symbol={"live": {"au": ["simple_strategy"]}, "sandbox": {}},
        warning_codes=warnings or [],
    )


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
                "reason": "tqkq_live_partial_fill",
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


def test_quote_mapping_separates_market_and_execution_prices() -> None:
    projection = _projection(
        orders=[
            {
                "order_id": "o1",
                "symbol": "au",
                "trade_instrument_id": "SHFE.au2406",
                "price": 449.0,
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
    assert projection["quotes"]["live"]["by_contract"]["SHFE.au2406"] is quote

    missing = _projection()["quotes"]["live"]["by_symbol"]["au"]
    assert missing["available"] is False
    assert missing["reason"] == "quote_not_recorded"


def test_active_symbols_falls_back_to_strategy_switch_proposal() -> None:
    projection = _projection(
        rank=[],
        proposal={"active_top_n_symbols": ["au"]},
    )

    active = projection["active_symbols"]["live"]
    assert active["symbols"] == ["au"]
    assert active["source"] == "strategy_switch_proposal"


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
    return source[start: next_start if next_start != -1 else len(source)]


def test_ui_core_dashboard_sections_consume_projection_contract() -> None:
    source = Path("web/ui/app.js").read_text(encoding="utf-8")

    assert 'projectionItems("positions")' in _function_body(source, "positionsTable")
    assert 'projectionItems("pending_orders")' in _function_body(source, "pendingOrdersTable")
    assert "projection()?.alerts?.items" in _function_body(source, "alertsList")
    assert 'projectionLive("active_symbols")' in _function_body(source, "activeSymbolsForDisplay")

    assert "liveTails()" not in _function_body(source, "positionsTable")
    assert "state.dashboard.warnings" not in _function_body(source, "alertsList")
    assert "liveTails().order_events" not in _function_body(source, "candidateRows")
    assert "liveTails().order_lifecycle_events" not in _function_body(source, "candidateRows")
