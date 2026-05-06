from __future__ import annotations

from typing import Any

from domain.enums import PositionSide
from domain.state import PortfolioState, PositionKey, PositionState
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
    portfolio_obj: PortfolioState | None = None,
    lifecycle: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scoped: dict[str, list[dict[str, Any]]] = {"local": [], "dryrun": [], "live": []}
    latest_portfolios: dict[str, PortfolioState | None] = {
        "local": None,
        "dryrun": None,
        "live": None,
    }
    latest_portfolios[scope] = portfolio_obj
    scoped_lifecycle = [
        {
            "runtime_profile": scope,
            "datastore_scope": scope,
            "event_id": f"order_lifecycle-{idx}",
            "source": "contract",
            "payload_type": "order_lifecycle",
            **row,
        }
        for idx, row in enumerate(lifecycle or [])
    ]
    return build_dashboard_projection(
        runtime_id="rt_projection_contract",
        plan_cfg=_plan(scope),
        execution={},
        portfolio={"local": None, "dryrun": None, "live": {}},
        latest_portfolios=latest_portfolios,
        event_stats={"local": {}, "dryrun": {}, "live": {}},
        lifecycle_events={**scoped, scope: scoped_lifecycle},
        order_events=scoped,
        fill_events=scoped,
        rank_events=scoped,
        strategy_score_events=scoped,
        lifecycle_stats={"local": {}, "dryrun": {}, "live": {}},
        risk_stats={"local": {}, "dryrun": {}, "live": {}},
        top_lifecycle_reject_reasons={"local": [], "dryrun": [], "live": []},
        strategy_switch_proposal=None,
        strategy_switch_approved=None,
        strategy_switch_rejected=None,
        enabled_strategies_by_symbol={"local": {}, "dryrun": {}, "live": {}},
        warning_codes=[],
    )


def _portfolio_with_position() -> PortfolioState:
    key = PositionKey("au", "SHFE.au2406", PositionSide.LONG)
    return PortfolioState(
        runtime_id="rt_projection_contract",
        positions={
            key: PositionState(
                instrument_id="au",
                trade_instrument_id="SHFE.au2406",
                position_side=PositionSide.LONG,
                quantity=2.0,
                avg_price=450.0,
                updated_ts=1,
            )
        },
    )


def test_broker_sync_observation_does_not_enter_positions() -> None:
    portfolio = PortfolioState(
        runtime_id="rt_projection_contract",
        metadata={"portfolio_sync": {"positions_qty_by_symbol": {"au": 3.0}}},
    )

    projection = _projection(portfolio_obj=portfolio)

    assert projection["positions"]["live"]["items"] == []
    diagnostics = projection["broker_sync_diagnostics"]["live"]
    assert diagnostics["is_source_of_truth"] is False
    assert diagnostics["items"][0]["symbol"] == "au"
    assert diagnostics["items"][0]["diagnostic_only"] is True


def test_pending_submitted_rejected_lifecycle_does_not_create_positions() -> None:
    projection = _projection(
        lifecycle=[
            {"order_id": "o1", "symbol": "au", "status": "NEW", "quantity": 1.0, "ts": 1},
            {"order_id": "o1", "symbol": "au", "status": "SUBMITTED", "quantity": 1.0, "ts": 2},
            {"order_id": "o2", "symbol": "au", "status": "REJECTED", "quantity": 1.0, "ts": 3},
        ],
    )

    assert projection["positions"]["live"]["items"] == []
    assert projection["pending_orders"]["live"]["count"] == 1
    assert projection["order_status"]["live"]["counts"] == {"SUBMITTED": 1, "REJECTED": 1}


def test_positions_only_come_from_portfolio_state_snapshot() -> None:
    projection = _projection(portfolio_obj=_portfolio_with_position())

    positions = projection["positions"]["live"]
    assert positions["is_source_of_truth"] is True
    assert positions["source"] == "portfolio_snapshot"
    assert positions["items"][0]["source"] == "portfolio_snapshot"
    assert positions["items"][0]["is_source_of_truth"] is True
    assert positions["items"][0]["quantity"] == 2.0
