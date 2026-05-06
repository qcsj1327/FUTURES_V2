from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, time
from typing import Any

from core.instruments.calendar import TradingCalendar, TradingSession

TERMINAL_ORDER_STATUSES = {"FILLED", "REJECTED", "EXPIRED", "CANCELED"}
PENDING_ORDER_STATUSES = {"NEW", "SUBMITTED", "PARTIAL"}
RUNTIME_SCOPES = ("local", "dryrun", "live")
OPTIONAL_ARTIFACT_WARNING_CODES = {
    "missing_candidate_summary",
    "missing_decision",
    "missing_approved",
    "missing_strategy_switch_approved",
    "missing_strategy_switch_rejected",
}


def build_dashboard_projection(
    *,
    runtime_id: str,
    plan_cfg: dict[str, Any],
    execution: dict[str, Any],
    portfolio: dict[str, dict[str, Any] | None],
    latest_portfolios: dict[str, Any | None],
    event_stats: dict[str, dict[str, Any]],
    lifecycle_events: dict[str, list[dict[str, Any]]],
    order_events: dict[str, list[dict[str, Any]]],
    fill_events: dict[str, list[dict[str, Any]]],
    rank_events: dict[str, list[dict[str, Any]]],
    strategy_score_events: dict[str, list[dict[str, Any]]],
    lifecycle_stats: dict[str, dict[str, Any]],
    risk_stats: dict[str, dict[str, Any]],
    top_lifecycle_reject_reasons: dict[str, list[dict[str, Any]]],
    strategy_switch_proposal: dict[str, Any] | None,
    strategy_switch_approved: dict[str, Any] | None,
    strategy_switch_rejected: dict[str, Any] | None,
    enabled_strategies_by_symbol: dict[str, dict[str, list[str]]],
    warning_codes: list[str],
    audit_projection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scoped_lifecycle_events = {
        scope: _events_for_scope(lifecycle_events.get(scope, []), scope)
        for scope in RUNTIME_SCOPES
    }
    scoped_order_events = {
        scope: _events_for_scope(order_events.get(scope, []), scope)
        for scope in RUNTIME_SCOPES
    }
    scoped_fill_events = {
        scope: _events_for_scope(fill_events.get(scope, []), scope)
        for scope in RUNTIME_SCOPES
    }
    scoped_rank_events = {
        scope: _events_for_scope(rank_events.get(scope, []), scope)
        for scope in RUNTIME_SCOPES
    }
    scoped_strategy_score_events = {
        scope: _events_for_scope(strategy_score_events.get(scope, []), scope)
        for scope in RUNTIME_SCOPES
    }
    projection = {
        "schema_version": 1,
        "runtime_id": runtime_id,
        "execution_state": _execution_state(
            plan_cfg=plan_cfg,
            execution=execution,
            event_stats=event_stats,
            lifecycle_events=scoped_lifecycle_events,
        ),
        "portfolio": portfolio,
        "positions": {
            scope: _project_positions(
                scope=scope,
                portfolio_summary=portfolio.get(scope),
                portfolio_obj=latest_portfolios.get(scope),
            )
            for scope in RUNTIME_SCOPES
        },
        "broker_sync_diagnostics": {
            scope: _project_broker_sync_diagnostics(
                scope=scope,
                portfolio_obj=latest_portfolios.get(scope),
            )
            for scope in RUNTIME_SCOPES
        },
        "pending_orders": {
            scope: _project_pending_orders(
                scope=scope,
                plan_cfg=plan_cfg,
                lifecycle_events=scoped_lifecycle_events.get(scope, []),
                order_events=scoped_order_events.get(scope, []),
            )
            for scope in RUNTIME_SCOPES
        },
        "order_status": {
            scope: _project_order_status(
                scoped_lifecycle_events.get(scope, []),
                scope=scope,
            )
            for scope in RUNTIME_SCOPES
        },
        "quotes": {
            scope: _project_quotes(
                scope=scope,
                plan_cfg=plan_cfg,
                lifecycle_events=scoped_lifecycle_events.get(scope, []),
                order_events=scoped_order_events.get(scope, []),
                fill_events=scoped_fill_events.get(scope, []),
                strategy_score_events=scoped_strategy_score_events.get(scope, []),
            )
            for scope in RUNTIME_SCOPES
        },
        "lifecycle_view": {
            scope: _project_lifecycle_view(
                scoped_lifecycle_events.get(scope, []),
                scope=scope,
            )
            for scope in RUNTIME_SCOPES
        },
        "strategy_scores": {
            scope: _project_strategy_scores(
                scoped_strategy_score_events.get(scope, []),
                scope=scope,
            )
            for scope in RUNTIME_SCOPES
        },
        "lifecycle_summary": lifecycle_stats,
        "risk_summary": {
            scope: {
                **(risk_stats.get(scope, {}) or {}),
                "top_risk_reject_reasons": top_lifecycle_reject_reasons.get(scope, []),
            }
            for scope in RUNTIME_SCOPES
        },
        "alerts": _project_alerts(
            warning_codes=warning_codes,
            top_lifecycle_reject_reasons=top_lifecycle_reject_reasons,
            audit_projection=audit_projection,
        ),
        "audit": _project_audit(audit_projection),
        "readiness": _project_readiness(audit_projection),
        "active_symbols": {
            scope: _project_active_symbols(
                scope=scope,
                plan_cfg=plan_cfg,
                rank_events=scoped_rank_events.get(scope, []),
                strategy_switch_proposal=(
                    strategy_switch_proposal if scope == _runtime_scope(plan_cfg) else None
                ),
            )
            for scope in RUNTIME_SCOPES
        },
        "strategy_switch": {
            **_project_strategy_switch_state(
                plan_cfg=plan_cfg,
                strategy_switch_proposal=strategy_switch_proposal,
                strategy_switch_approved=strategy_switch_approved,
                strategy_switch_rejected=strategy_switch_rejected,
            ),
            "proposal": strategy_switch_proposal,
            "approved": strategy_switch_approved,
            "rejected": strategy_switch_rejected,
            "enabled_strategies_by_symbol": (
                _approved_enabled_by_symbol(strategy_switch_approved)
                or enabled_strategies_by_symbol.get(_runtime_scope(plan_cfg), {})
            ),
        },
    }
    return projection


def _execution_state(
    *,
    plan_cfg: dict[str, Any],
    execution: dict[str, Any],
    event_stats: dict[str, dict[str, Any]],
    lifecycle_events: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    runtime_raw = plan_cfg.get("runtime")
    runtime = runtime_raw if isinstance(runtime_raw, dict) else {}
    scope = _runtime_scope(plan_cfg)
    scope_stats = event_stats.get(scope, {})
    return {
        "runtime_mode": runtime.get("mode"),
        "runtime_profile": scope,
        "datastore_scope": scope,
        "broker_type": execution.get("broker_type"),
        "execution_mode": execution.get("execution_mode"),
        "confirm_live": execution.get("confirm_live") is True,
        "confirm_live_token_present": execution.get("confirm_live_token_present") is True,
        "pending_orders_count": _pending_count(lifecycle_events.get(scope, [])),
        "fill_events_count": int(scope_stats.get("fill_events_lines", 0) or 0),
        "source": "manifest_plan",
    }


def _runtime_scope(plan_cfg: dict[str, Any]) -> str:
    runtime = plan_cfg.get("runtime")
    mode = runtime.get("mode") if isinstance(runtime, Mapping) else None
    if mode not in RUNTIME_SCOPES:
        raise ValueError(f"invalid runtime mode for projection: {mode!r}")
    return str(mode)


def _events_for_scope(events: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for event in events:
        runtime_profile = _str_or_none(event.get("runtime_profile"))
        datastore_scope = _str_or_none(event.get("datastore_scope"))
        if runtime_profile is None or datastore_scope is None:
            continue
        if runtime_profile != scope:
            continue
        if datastore_scope != scope:
            continue
        out.append(event)
    return out


def _section_source(
    *,
    scope: str,
    source: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    source_event_ids = [
        event_id
        for event in events
        if isinstance((event_id := _str_or_none(event.get("event_id"))), str)
    ]
    source_scope_unknown_count = 0
    invalid_projection_source_count = 0
    payload_types: set[str] = set()
    sources: set[str] = set()
    for event in events:
        payload_type = _str_or_none(event.get("payload_type"))
        if payload_type:
            payload_types.add(payload_type)
        event_source = _str_or_none(event.get("source"))
        if event_source:
            sources.add(event_source)
        runtime_profile = _str_or_none(event.get("runtime_profile"))
        datastore_scope = _str_or_none(event.get("datastore_scope"))
        if runtime_profile is None or datastore_scope is None:
            source_scope_unknown_count += 1
            continue
        if runtime_profile != scope or datastore_scope != scope:
            invalid_projection_source_count += 1
    return {
        "runtime_profile": scope,
        "datastore_scope": scope,
        "source": source,
        "source_event_ids": source_event_ids,
        "source_scope_unknown": source_scope_unknown_count > 0,
        "source_scope_unknown_count": source_scope_unknown_count,
        "invalid_projection_source_count": invalid_projection_source_count,
        "payload_types": sorted(payload_types),
        "event_sources": sorted(sources),
    }


def _item_source(
    event: Mapping[str, Any],
    *,
    scope: str,
    fallback_source: str,
) -> dict[str, Any]:
    runtime_profile = _str_or_none(event.get("runtime_profile"))
    datastore_scope = _str_or_none(event.get("datastore_scope"))
    source_scope_unknown = runtime_profile is None or datastore_scope is None
    return {
        "runtime_profile": runtime_profile,
        "datastore_scope": datastore_scope,
        "source_event_id": _str_or_none(event.get("event_id")),
        "source": _str_or_none(event.get("source")) or fallback_source,
        "payload_type": _str_or_none(event.get("payload_type")),
        "source_scope_unknown": source_scope_unknown,
        "invalid_projection_source": (
            not source_scope_unknown
            and (runtime_profile != scope or datastore_scope != scope)
        ),
    }


def _project_positions(
    *,
    scope: str,
    portfolio_summary: dict[str, Any] | None,
    portfolio_obj: Any | None,
) -> dict[str, Any]:
    items = _positions_from_portfolio_snapshot(portfolio_obj, scope=scope)
    if items:
        return {
            **_section_source(scope=scope, source="portfolio_snapshot", events=[]),
            "items": items,
            "empty_reason": None,
            "is_source_of_truth": True,
        }

    empty_reason = "no_filled_position"
    if portfolio_summary is None and portfolio_obj is None:
        empty_reason = "no_portfolio_snapshot"
    return {
        **_section_source(scope=scope, source="portfolio_snapshot", events=[]),
        "items": [],
        "empty_reason": empty_reason,
        "is_source_of_truth": True,
    }


def _positions_from_portfolio_snapshot(
    portfolio_obj: Any | None,
    *,
    scope: str,
) -> list[dict[str, Any]]:
    positions = getattr(portfolio_obj, "positions", None)
    if not isinstance(positions, Mapping):
        return []
    out: list[dict[str, Any]] = []
    for pos in positions.values():
        quantity = _number(getattr(pos, "quantity", None))
        if quantity is None or quantity <= 0:
            continue
        symbol = getattr(pos, "instrument_id", None)
        trade_id = getattr(pos, "trade_instrument_id", None)
        if not isinstance(symbol, str) or not symbol:
            continue
        out.append(
            {
                "symbol": symbol,
                "trade_instrument_id": trade_id if isinstance(trade_id, str) else None,
                "position_side": _enum_value(getattr(pos, "position_side", None)),
                "quantity": quantity,
                "avg_price": _number(getattr(pos, "avg_price", None)),
                "unrealized_pnl": _number(getattr(pos, "unrealized_pnl", None)),
                "realized_pnl": _number(getattr(pos, "realized_pnl", None)),
                "updated_ts": getattr(pos, "updated_ts", None),
                "source": "portfolio_snapshot",
                "runtime_profile": scope,
                "datastore_scope": scope,
                "source_event_id": None,
                "is_source_of_truth": True,
            }
        )
    return sorted(out, key=lambda x: (str(x.get("symbol")), str(x.get("trade_instrument_id"))))


def _project_broker_sync_diagnostics(
    *,
    scope: str,
    portfolio_obj: Any | None,
) -> dict[str, Any]:
    items = _broker_sync_observation_items(portfolio_obj, scope=scope)
    return {
        **_section_source(scope=scope, source="broker_sync_observation", events=[]),
        "items": items,
        "count": len(items),
        "is_source_of_truth": False,
        "empty_reason": None if items else "no_broker_sync_observation",
    }


def _broker_sync_observation_items(
    portfolio_obj: Any | None,
    *,
    scope: str,
) -> list[dict[str, Any]]:
    metadata = getattr(portfolio_obj, "metadata", None)
    if not isinstance(metadata, Mapping):
        return []
    sync = metadata.get("portfolio_sync")
    if not isinstance(sync, Mapping):
        return []
    positions = sync.get("positions_qty_by_symbol")
    if not isinstance(positions, Mapping):
        return []
    out: list[dict[str, Any]] = []
    for symbol, qty_raw in positions.items():
        qty = _number(qty_raw)
        if not isinstance(symbol, str) or qty is None or qty == 0:
            continue
        out.append(
            {
                "symbol": symbol,
                "trade_instrument_id": None,
                "position_side": "unknown",
                "quantity": abs(qty),
                "avg_price": None,
                "unrealized_pnl": None,
                "realized_pnl": None,
                "updated_ts": getattr(portfolio_obj, "updated_ts", None),
                "source": "broker_sync_observation",
                "runtime_profile": scope,
                "datastore_scope": scope,
                "is_source_of_truth": False,
                "diagnostic_only": True,
            }
        )
    return sorted(out, key=lambda x: str(x.get("symbol")))


def _project_pending_orders(
    *,
    scope: str,
    plan_cfg: dict[str, Any],
    lifecycle_events: list[dict[str, Any]],
    order_events: list[dict[str, Any]],
) -> dict[str, Any]:
    order_by_key = _order_lookup(order_events)
    latest: dict[str, dict[str, Any]] = {}
    for event in lifecycle_events:
        order_id = event.get("order_id")
        if isinstance(order_id, str) and order_id:
            latest[order_id] = event

    items: list[dict[str, Any]] = []
    for order_id, event in latest.items():
        status = str(event.get("status", ""))
        if status not in PENDING_ORDER_STATUSES or status in TERMINAL_ORDER_STATUSES:
            continue
        base_order = order_by_key.get(order_id) or order_by_key.get(_order_match_key(event)) or {}
        remaining = _number(event.get("remaining_quantity"))
        quantity = _number(event.get("quantity"))
        filled = _number(event.get("filled_quantity"))
        if filled is None:
            filled = 0.0
        if remaining is None and quantity is not None and filled is not None:
            remaining = max(0.0, quantity - filled)
        avg_fill_price = _number(event.get("avg_fill_price")) or _number(
            base_order.get("avg_fill_price")
        )
        latest_market_price = (
            _number(event.get("latest_market_price"))
            or _number(event.get("market_price"))
            or _number(base_order.get("latest_market_price"))
            or _number(base_order.get("market_price"))
        )
        side = _str_or_none(event.get("side")) or _str_or_none(base_order.get("side"))
        position_side = _str_or_none(event.get("position_side")) or _str_or_none(
            base_order.get("position_side")
        )
        item = {
            "order_id": order_id,
            "symbol": _str_or_none(event.get("symbol"))
            or _str_or_none(event.get("instrument_id"))
            or _str_or_none(base_order.get("symbol"))
            or _str_or_none(base_order.get("instrument_id")),
            "trade_instrument_id": _str_or_none(event.get("trade_instrument_id"))
            or _str_or_none(base_order.get("trade_instrument_id")),
            "side": side,
            "position_side": position_side,
            "quantity": quantity,
            "filled_quantity": filled,
            "remaining_quantity": remaining,
            "avg_fill_price": avg_fill_price,
            "latest_market_price": latest_market_price,
            "unrealized_pnl": _order_unrealized_pnl(
                side=side,
                position_side=position_side,
                filled_quantity=filled,
                avg_fill_price=avg_fill_price,
                latest_market_price=latest_market_price,
            ),
            "status": status,
            "reason": _str_or_none(event.get("reason")),
            "order_price": _number(event.get("price")) or _number(base_order.get("price")),
            "stop_loss": _number(event.get("stop_loss"))
            or _number(event.get("stop_loss_price"))
            or _number(base_order.get("stop_loss"))
            or _number(base_order.get("stop_loss_price")),
            "take_profit": _number(event.get("take_profit"))
            or _number(event.get("take_profit_price"))
            or _number(base_order.get("take_profit"))
            or _number(base_order.get("take_profit_price")),
            "ts": event.get("ts"),
            **_item_source(event, scope=scope, fallback_source="order_lifecycle_events"),
        }
        items.append(item)
    items.sort(key=lambda x: (int(x["ts"]) if isinstance(x.get("ts"), int) else 0, x["order_id"]))
    return {
        **_section_source(
            scope=scope,
            source="order_lifecycle_events",
            events=[*lifecycle_events, *order_events],
        ),
        "items": items,
        "count": len(items),
    }


def _order_unrealized_pnl(
    *,
    side: str | None,
    position_side: str | None,
    filled_quantity: float | None,
    avg_fill_price: float | None,
    latest_market_price: float | None,
) -> float | None:
    if (
        filled_quantity is None
        or filled_quantity <= 0
        or avg_fill_price is None
        or latest_market_price is None
    ):
        return None
    is_short = position_side == "short" or side == "sell"
    if is_short:
        return (avg_fill_price - latest_market_price) * filled_quantity
    return (latest_market_price - avg_fill_price) * filled_quantity


def _project_order_status(
    lifecycle_events: list[dict[str, Any]],
    *,
    scope: str,
) -> dict[str, Any]:
    latest: dict[str, dict[str, Any]] = {}
    for event in lifecycle_events:
        order_id = event.get("order_id")
        if isinstance(order_id, str) and order_id:
            old = latest.get(order_id)
            if old is None or _event_ts(event) >= _event_ts(old):
                latest[order_id] = event

    counts = Counter(str(event.get("status", "")) for event in latest.values())
    counts.pop("", None)
    def _sort_pending_item(item: dict[str, Any]) -> tuple[int, str]:
        ts = item.get("ts")
        return (ts if isinstance(ts, int) else 0, str(item.get("order_id")))

    items = sorted(
        (
            {
                "order_id": order_id,
                "status": str(event.get("status", "")),
                "symbol": _str_or_none(event.get("symbol"))
                or _str_or_none(event.get("instrument_id")),
                "ts": event.get("ts"),
                "reason": _str_or_none(event.get("reason")),
                **_item_source(event, scope=scope, fallback_source="order_lifecycle_events"),
            }
            for order_id, event in latest.items()
        ),
        key=_sort_pending_item,
    )
    return {
        **_section_source(scope=scope, source="order_lifecycle_events", events=lifecycle_events),
        "counts": dict(counts),
        "items": items,
        "count": len(items),
    }


def _project_quotes(
    *,
    scope: str,
    plan_cfg: dict[str, Any],
    lifecycle_events: list[dict[str, Any]],
    order_events: list[dict[str, Any]],
    fill_events: list[dict[str, Any]],
    strategy_score_events: list[dict[str, Any]],
) -> dict[str, Any]:
    latest_ts = _latest_event_ts(
        [*order_events, *lifecycle_events, *fill_events, *strategy_score_events]
    )
    contracts = _contracts(plan_cfg, ts=latest_ts)
    symbols = set(_universe_symbols(plan_cfg)) | set(contracts)
    for event in [*order_events, *lifecycle_events, *fill_events, *strategy_score_events]:
        sym = _str_or_none(event.get("symbol")) or _str_or_none(event.get("instrument_id"))
        if sym:
            symbols.add(sym)

    event_rows = [*order_events, *lifecycle_events, *fill_events, *strategy_score_events]
    latest_market_by_key: dict[str, tuple[int, float, str]] = {}
    latest_exec_by_key: dict[str, tuple[int, float, str]] = {}
    latest_order_price_by_key: dict[str, tuple[int, float]] = {}
    latest_stop_loss_by_key: dict[str, tuple[int, float]] = {}
    latest_take_profit_by_key: dict[str, tuple[int, float]] = {}
    contract_by_symbol = dict(contracts)
    for event in event_rows:
        symbol = _str_or_none(event.get("symbol")) or _str_or_none(event.get("instrument_id"))
        contract = _str_or_none(event.get("trade_instrument_id"))
        if symbol and contract:
            if _is_main_alias(contract):
                contract_by_symbol.setdefault(symbol, contract)
            else:
                contract_by_symbol[symbol] = contract
        keys = [x for x in (symbol, contract) if x]
        ts = _event_ts(event)
        market_ts = _market_event_ts(event)
        market_price = _number(event.get("latest_market_price"))
        if market_price is None:
            market_price = _number(event.get("market_price"))
        if market_price is not None:
            for key in keys:
                _set_latest(
                    latest_market_by_key,
                    key,
                    market_ts,
                    market_price,
                    "market_price",
                )
        exec_price = _number(event.get("fill_price"))
        exec_source = "fill_price"
        if exec_price is None:
            exec_price = _number(event.get("avg_fill_price"))
            exec_source = "avg_fill_price"
        if exec_price is not None:
            for key in keys:
                _set_latest(latest_exec_by_key, key, ts, exec_price, exec_source)
        order_price = _number(event.get("price"))
        if order_price is not None:
            for key in keys:
                old = latest_order_price_by_key.get(key)
                if old is None or ts >= old[0]:
                    latest_order_price_by_key[key] = (ts, order_price)
        stop_loss = _number(event.get("stop_loss"))
        if stop_loss is None:
            stop_loss = _number(event.get("stop_loss_price"))
        if stop_loss is not None:
            for key in keys:
                old = latest_stop_loss_by_key.get(key)
                if old is None or ts >= old[0]:
                    latest_stop_loss_by_key[key] = (ts, stop_loss)
        take_profit = _number(event.get("take_profit"))
        if take_profit is None:
            take_profit = _number(event.get("take_profit_price"))
        if take_profit is not None:
            for key in keys:
                old = latest_take_profit_by_key.get(key)
                if old is None or ts >= old[0]:
                    latest_take_profit_by_key[key] = (ts, take_profit)

    items: list[dict[str, Any]] = []
    for symbol in sorted(symbols):
        contract = contract_by_symbol.get(symbol) or contracts.get(symbol)
        market = latest_market_by_key.get(symbol) or (
            latest_market_by_key.get(contract) if contract else None
        )
        execution = latest_exec_by_key.get(symbol) or (
            latest_exec_by_key.get(contract) if contract else None
        )
        order_price_row = latest_order_price_by_key.get(symbol) or (
            latest_order_price_by_key.get(contract) if contract else None
        )
        stop_loss_row = latest_stop_loss_by_key.get(symbol) or (
            latest_stop_loss_by_key.get(contract) if contract else None
        )
        take_profit_row = latest_take_profit_by_key.get(symbol) or (
            latest_take_profit_by_key.get(contract) if contract else None
        )
        available = market is not None
        reason = "ok" if available else "quote_not_recorded"
        if not contract:
            reason = "contract_quote_unmapped"
        tradability = _project_tradability(
            plan_cfg=plan_cfg,
            symbol=symbol,
            ts=market[0] if market else latest_ts,
            lifecycle_events=lifecycle_events,
            has_market=available,
        )
        items.append(
            {
                "symbol": symbol,
                "trade_instrument_id": contract,
                "latest_market_price": market[1] if market else None,
                "last_execution_price": execution[1] if execution else None,
                "order_price": order_price_row[1] if order_price_row else None,
                "stop_loss": stop_loss_row[1] if stop_loss_row else None,
                "take_profit": take_profit_row[1] if take_profit_row else None,
                "available": available,
                "price_source": market[2] if market else "none",
                "execution_price_source": execution[2] if execution else "none",
                "reason": reason,
                "tradability": tradability,
                "runtime_profile": scope,
                "datastore_scope": scope,
            }
        )
    by_symbol = {str(item["symbol"]): item for item in items if item.get("symbol")}
    by_contract = {
        str(item["trade_instrument_id"]): item
        for item in items
        if item.get("trade_instrument_id")
    }
    return {
        **_section_source(
            scope=scope,
            source="quote_projection",
            events=[*order_events, *lifecycle_events, *fill_events, *strategy_score_events],
        ),
        "items": items,
        "by_symbol": by_symbol,
        "by_contract": by_contract,
    }


def _project_tradability(
    *,
    plan_cfg: dict[str, Any],
    symbol: str,
    ts: int,
    lifecycle_events: list[dict[str, Any]],
    has_market: bool,
) -> dict[str, Any]:
    for event in reversed(lifecycle_events[-200:]):
        event_symbol = _str_or_none(event.get("symbol")) or _str_or_none(event.get("instrument_id"))
        if event_symbol != symbol:
            continue
        reason = _str_or_none(event.get("reason")) or ""
        message = " ".join(
            str(event.get(key) or "")
            for key in ("message", "error", "raw_reason", "status_msg")
        )
        if reason == "non_trading_time" or "不在可交易时间" in message:
            return {
                "state": "non_trading_time",
                "reason": reason or "non_trading_time",
                "source": "order_lifecycle_events",
                "next_action": "等待交易时段",
            }
    if _runtime_scope(plan_cfg) == "local":
        if has_market:
            return {
                "state": "tradable",
                "reason": "local_simulated_quote_available",
                "source": "local_simulated_quote",
                "next_action": "等待价格触发",
            }
        return {
            "state": "unknown",
            "reason": "quote_not_recorded",
            "source": "projection",
            "next_action": "等待行情确认",
        }
    if _has_trading_sessions(plan_cfg, symbol) and not _is_trading_time_by_plan(
        plan_cfg,
        symbol,
        ts,
    ):
        return {
            "state": "non_trading_time",
            "reason": "non_trading_time",
            "source": "trading_sessions",
            "next_action": "等待交易时段",
        }
    if has_market:
        return {
            "state": "tradable",
            "reason": "market_quote_available",
            "source": "market_quote",
            "next_action": "等待价格触发",
        }
    return {
        "state": "unknown",
        "reason": "quote_not_recorded",
        "source": "projection",
        "next_action": "等待行情确认",
    }


def _has_trading_sessions(plan_cfg: dict[str, Any], symbol: str) -> bool:
    return bool(_trading_sessions(plan_cfg, symbol))


def _is_trading_time_by_plan(plan_cfg: dict[str, Any], symbol: str, ts: int) -> bool:
    sessions = _trading_sessions(plan_cfg, symbol)
    if not sessions:
        return True
    if ts <= 0:
        return False
    base = _base_symbol(symbol)
    calendar = TradingCalendar(
        sessions_by_symbol={
            base: [
                TradingSession(start=session["start"], end=session["end"])
                for session in sessions
            ]
        }
    )
    return calendar.is_trading_time(base, ts)


def _trading_sessions(plan_cfg: dict[str, Any], symbol: str) -> list[dict[str, str]]:
    base = _base_symbol(symbol)
    instruments = plan_cfg.get("instruments")
    if not isinstance(instruments, dict):
        return []
    raw = instruments.get("trading_sessions")
    if not isinstance(raw, dict):
        return []
    sessions = raw.get(base)
    if not isinstance(sessions, list):
        return []
    out: list[dict[str, str]] = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
        start = session.get("start")
        end = session.get("end")
        if isinstance(start, str) and isinstance(end, str):
            out.append({"start": start, "end": end})
    return out


def _parse_hhmm(value: str | None) -> time | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        return None


def _base_symbol(value: str) -> str:
    if value.startswith("KQ.m@"):
        value = value.removeprefix("KQ.m@")
    if "." in value:
        value = value.rsplit(".", 1)[1]
    return "".join(ch for ch in value if ch.isalpha()) or value


def _project_lifecycle_view(
    lifecycle_events: list[dict[str, Any]],
    *,
    scope: str,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    folded: Counter[str] = Counter()
    latest_folded: dict[str, dict[str, Any]] = {}
    for event in lifecycle_events:
        reason = _str_or_none(event.get("reason"))
        if reason == "blocked_by_pending_order":
            symbol = (
                _str_or_none(event.get("symbol"))
                or _str_or_none(event.get("instrument_id"))
                or ""
            )
            key = "|".join([symbol, reason])
            folded[key] += 1
            latest_folded[key] = event
            continue
        items.append(
            {
                **event,
                **_item_source(event, scope=scope, fallback_source="order_lifecycle_events"),
            }
        )

    for key, count in folded.items():
        event = {
            **latest_folded[key],
            **_item_source(
                latest_folded[key],
                scope=scope,
                fallback_source="order_lifecycle_events",
            ),
        }
        event["folded_count"] = count
        event["display_reason"] = "blocked_by_pending_order"
        items.append(event)

    items.sort(key=_event_ts)
    return {
        **_section_source(scope=scope, source="order_lifecycle_events", events=lifecycle_events),
        "items": items,
        "folded_rejects": [
            {
                "key": key,
                "reason": "blocked_by_pending_order",
                "count": count,
            }
            for key, count in sorted(folded.items())
        ],
    }


def _project_strategy_scores(
    events: list[dict[str, Any]],
    *,
    scope: str,
) -> dict[str, Any]:
    section = _section_source(scope=scope, source="strategy_score_events", events=events)
    latest_ts = max((_event_ts(event) for event in events), default=None)
    if latest_ts is None:
        return {**section, "items": [], "latest_by_symbol": {}}

    items: list[dict[str, Any]] = []
    for event in events:
        if _event_ts(event) != latest_ts:
            continue
        symbol = _str_or_none(event.get("symbol")) or _str_or_none(event.get("instrument_id"))
        if not symbol:
            continue
        final_score = _number(event.get("final_score"))
        if final_score is None:
            final_score = _number(event.get("score"))
        items.append(
            {
                "symbol": symbol,
                "strategy_name": _str_or_none(event.get("strategy_name")),
                "strategy_id": _str_or_none(event.get("strategy_id"))
                or _str_or_none(event.get("strategy_name")),
                "decision": _str_or_none(event.get("decision")),
                "strength": _str_or_none(event.get("strength")),
                "confidence": _number(event.get("confidence")),
                "final_score": final_score,
                "raw_score": _number(event.get("raw_score")),
                "cost_penalty": _number(event.get("cost_penalty")),
                "risk_penalty": _number(event.get("risk_penalty")),
                "scoring_model": _str_or_none(event.get("scoring_model")),
                "ts": event.get("ts"),
                **_item_source(event, scope=scope, fallback_source="strategy_score_events"),
            }
        )
    items.sort(
        key=lambda item: (
            str(item.get("symbol")),
            -(item.get("final_score") or 0.0),
            str(item.get("strategy_id") or ""),
        )
    )
    latest_by_symbol: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        latest_by_symbol.setdefault(str(item["symbol"]), []).append(item)
    return {**section, "items": items, "latest_by_symbol": latest_by_symbol}


def _project_alerts(
    *,
    warning_codes: list[str],
    top_lifecycle_reject_reasons: dict[str, list[dict[str, Any]]],
    audit_projection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    optional: list[dict[str, Any]] = []
    for code in warning_codes:
        warning = _warning_item(code)
        if code in OPTIONAL_ARTIFACT_WARNING_CODES or code.startswith(
            tuple(f"{x}_file:" for x in OPTIONAL_ARTIFACT_WARNING_CODES)
        ):
            optional.append(warning)
        else:
            items.append(warning)

    for scope, reasons in top_lifecycle_reject_reasons.items():
        for reason in reasons:
            code = _str_or_none(reason.get("reason")) or "unknown_reject_reason"
            count = int(reason.get("count", 0) or 0)
            level = "error" if code.startswith("risk_") or code == "halted_by_guard" else "warning"
            items.append(
                {
                    "code": code,
                    "level": level,
                    "message": f"{code} occurred {count} time(s)",
                    "source": f"{scope}.order_lifecycle_events",
                    "count": count,
                }
            )
    counts = Counter(str(item.get("level", "info")) for item in items)
    for alert in _audit_alert_items(audit_projection):
        items.append(alert)
    counts = Counter(str(item.get("level", "info")) for item in items)
    return {
        "items": items,
        "optional_warnings": optional,
        "counts": {
            "error": counts.get("error", 0),
            "warning": counts.get("warning", 0),
            "info": counts.get("info", 0),
        },
    }


def _project_audit(audit_projection: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(audit_projection, dict):
        return {
            "source": "audit_artifact",
            "is_source_of_truth": False,
            "mutation_allowed": False,
            "diagnostic_only": True,
            "audit": None,
            "alerts": [],
        }
    audit = audit_projection.get("audit")
    return {
        "source": "audit_artifact",
        "is_source_of_truth": False,
        "mutation_allowed": False,
        "diagnostic_only": audit_projection.get("diagnostic_only") is True,
        "audit": audit if isinstance(audit, dict) else None,
        "alerts": _audit_alert_items(audit_projection),
    }


def _project_readiness(audit_projection: dict[str, Any] | None) -> dict[str, Any]:
    readiness = audit_projection.get("readiness") if isinstance(audit_projection, dict) else None
    if not isinstance(readiness, dict):
        return {
            "source": "audit_artifact",
            "is_source_of_truth": False,
            "mutation_allowed": False,
            "status": None,
            "checks": {},
            "diagnostics": [],
        }
    return {
        "source": "audit_artifact",
        "is_source_of_truth": False,
        "mutation_allowed": False,
        "status": readiness.get("status"),
        "checks": readiness.get("checks") if isinstance(readiness.get("checks"), dict) else {},
        "diagnostics": (
            readiness.get("diagnostics") if isinstance(readiness.get("diagnostics"), list) else []
        ),
    }


def _audit_alert_items(audit_projection: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(audit_projection, dict):
        return []
    alerts = audit_projection.get("alerts")
    if not isinstance(alerts, list):
        return []
    out: list[dict[str, Any]] = []
    for alert in alerts:
        if not isinstance(alert, dict):
            continue
        out.append(
            {
                **alert,
                "source": "audit_artifact",
                "is_source_of_truth": False,
                "mutation_allowed": False,
            }
        )
    return out


def _project_strategy_switch_state(
    *,
    plan_cfg: dict[str, Any],
    strategy_switch_proposal: dict[str, Any] | None,
    strategy_switch_approved: dict[str, Any] | None,
    strategy_switch_rejected: dict[str, Any] | None,
) -> dict[str, Any]:
    strategies = plan_cfg.get("strategies")
    switch_cfg = plan_cfg.get("strategy_switch")
    switch_cfg = switch_cfg if isinstance(switch_cfg, Mapping) else {}
    if not isinstance(strategies, list) or not strategies:
        return {
            "state": "not_applicable",
            "state_reason": "no_strategies_configured",
            "approval_required": False,
        }
    approval_required_by_plan = switch_cfg.get("approval_required")
    approval_required_by_plan = (
        bool(approval_required_by_plan)
        if approval_required_by_plan is not None
        else _active_top_n(plan_cfg) > 0
    )
    if isinstance(strategy_switch_approved, dict):
        return {
            "state": "approved",
            "state_reason": "auto_promotion_approved",
            "approval_required": False,
        }
    if not approval_required_by_plan:
        return {
            "state": "disabled",
            "state_reason": "auto_promotion_waiting_for_scores",
            "approval_required": False,
        }
    if isinstance(strategy_switch_rejected, dict):
        return {
            "state": "rejected",
            "state_reason": "rejected_artifact_present",
            "approval_required": True,
        }
    if isinstance(strategy_switch_proposal, dict):
        thresholds = strategy_switch_proposal.get("thresholds")
        approval_required = (
            thresholds.get("approval_required") is True
            if isinstance(thresholds, Mapping)
            else False
        )
        if approval_required:
            return {
                "state": "proposal_pending",
                "state_reason": "proposal_requires_approval",
                "approval_required": True,
            }
    return {
        "state": "proposal_pending",
        "state_reason": "proposal_missing_or_waiting_for_scores",
        "approval_required": True,
    }


def _approved_enabled_by_symbol(
    strategy_switch_approved: dict[str, Any] | None,
) -> dict[str, list[str]]:
    if not isinstance(strategy_switch_approved, Mapping):
        return {}
    raw = strategy_switch_approved.get("enabled_strategies_by_symbol")
    if not isinstance(raw, Mapping):
        return {}
    out: dict[str, list[str]] = {}
    for symbol, names in raw.items():
        if not isinstance(symbol, str) or not isinstance(names, list):
            continue
        parsed = [name for name in names if isinstance(name, str) and name]
        if parsed:
            out[symbol] = parsed
    return out


def _project_active_symbols(
    *,
    scope: str,
    plan_cfg: dict[str, Any],
    rank_events: list[dict[str, Any]],
    strategy_switch_proposal: dict[str, Any] | None,
) -> dict[str, Any]:
    section = _section_source(scope=scope, source="rank_events", events=rank_events)
    latest_rank = rank_events[-1] if rank_events else None
    if isinstance(latest_rank, dict):
        active = latest_rank.get("active_symbols")
        if isinstance(active, list):
            symbols = sorted(x for x in active if isinstance(x, str))
            if symbols:
                return {
                    **section,
                    "symbols": symbols,
                    "source": "rank_events",
                    "explanation": "using latest rank_events.active_symbols",
                }
        scores = latest_rank.get("scores")
        if isinstance(scores, list):
            symbols = sorted(
                item["symbol"]
                for item in scores
                if isinstance(item, dict) and isinstance(item.get("symbol"), str)
            )
            if symbols:
                return {
                    **section,
                    "symbols": symbols,
                    "source": "rank_events_scores",
                    "explanation": "using latest rank_events.scores symbols",
                }

    if isinstance(strategy_switch_proposal, dict):
        raw = strategy_switch_proposal.get("active_top_n_symbols")
        if isinstance(raw, list):
            symbols = sorted(x for x in raw if isinstance(x, str))
            if symbols:
                return {
                    **_section_source(scope=scope, source="strategy_switch_proposal", events=[]),
                    "symbols": symbols,
                    "source": "strategy_switch_proposal",
                    "explanation": (
                        "rank_events missing; using "
                        "strategy_switch.proposal.active_top_n_symbols"
                    ),
                }

    universe = _universe_symbols(plan_cfg)
    if _active_top_n(plan_cfg) <= 0:
        return {
            **_section_source(scope=scope, source="universe", events=[]),
            "symbols": universe,
            "source": "universe",
            "explanation": "TopN disabled; using universe symbols",
        }
    return {
        **_section_source(scope=scope, source="none", events=[]),
        "symbols": [],
        "source": "none",
        "explanation": "TopN enabled but rank_events and strategy_switch proposal are empty",
    }


def _pending_count(lifecycle_events: list[dict[str, Any]]) -> int:
    count = _project_pending_orders(
        scope="live",
        plan_cfg={},
        lifecycle_events=lifecycle_events,
        order_events=[],
    )["count"]
    return count if isinstance(count, int) else 0


def _order_lookup(order_events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for event in order_events:
        order_id = event.get("order_id")
        if isinstance(order_id, str) and order_id:
            out[order_id] = event
        out[_order_match_key(event)] = event
    return out


def _order_match_key(event: Mapping[str, Any]) -> str:
    return "|".join(
        str(event.get(k) or "")
        for k in ("symbol", "instrument_id", "trade_instrument_id", "side", "position_side")
    )


def _set_latest(
    target: dict[str, tuple[int, float, str]],
    key: str,
    ts: int,
    value: float,
    source: str,
) -> None:
    old = target.get(key)
    if old is None or ts >= old[0]:
        target[key] = (ts, value, source)


def _event_ts(event: Mapping[str, Any]) -> int:
    ts = event.get("ts")
    return int(ts) if isinstance(ts, int) else 0


def _market_event_ts(event: Mapping[str, Any]) -> int:
    for key in ("market_ts", "quote_ts", "latest_market_ts"):
        ts = event.get(key)
        if isinstance(ts, int):
            return int(ts)
    return _event_ts(event)


def _warning_item(code: str) -> dict[str, str]:
    return {
        "code": code,
        "level": "info" if code.startswith("missing_") else "warning",
        "message": code,
        "source": "artifact",
    }


def _universe_symbols(plan_cfg: dict[str, Any]) -> list[str]:
    universe = plan_cfg.get("universe")
    if not isinstance(universe, dict):
        return []
    symbols = universe.get("symbols")
    if not isinstance(symbols, list):
        return []
    parsed = [x for x in symbols if isinstance(x, str)]
    return parsed


def _contracts(plan_cfg: dict[str, Any], *, ts: int = 0) -> dict[str, str]:
    instruments = plan_cfg.get("instruments")
    if not isinstance(instruments, dict):
        return {}
    roll = instruments.get("roll_policy")
    if not isinstance(roll, dict):
        return {}
    raw = roll.get("contracts")
    if not isinstance(raw, dict):
        raw = {}
    contracts = {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)}
    schedule_raw = roll.get("main_contract_schedule")
    schedule = schedule_raw if isinstance(schedule_raw, dict) else {}
    mode = roll.get("mode")
    out: dict[str, str] = {}
    for symbol, contract in contracts.items():
        values = schedule.get(symbol)
        if (
            mode == "fixed_main"
            and isinstance(values, list)
            and values
            and all(isinstance(value, str) and value for value in values)
        ):
            idx = max(0, min(int(ts), len(values) - 1))
            out[symbol] = values[idx]
        else:
            out[symbol] = contract
    return out


def _latest_event_ts(events: list[dict[str, Any]]) -> int:
    return max((_event_ts(event) for event in events), default=0)


def _is_main_alias(contract: str) -> bool:
    return contract.endswith("_main")


def _active_top_n(plan_cfg: dict[str, Any]) -> int:
    runtime = plan_cfg.get("runtime")
    if not isinstance(runtime, dict):
        return 0
    raw = runtime.get("active_top_n", 0)
    return int(raw) if isinstance(raw, (int, float)) else 0


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _str_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _enum_value(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    return raw if isinstance(raw, str) else None
