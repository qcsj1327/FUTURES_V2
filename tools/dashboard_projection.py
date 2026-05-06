from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any

TERMINAL_ORDER_STATUSES = {"FILLED", "REJECTED", "EXPIRED", "CANCELED"}
PENDING_ORDER_STATUSES = {"NEW", "SUBMITTED", "PARTIAL"}
OPTIONAL_ARTIFACT_WARNING_CODES = {
    "missing_candidate_summary",
    "missing_decision",
    "missing_approved",
    "missing_strategy_switch_approved",
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
    lifecycle_stats: dict[str, dict[str, Any]],
    risk_stats: dict[str, dict[str, Any]],
    top_lifecycle_reject_reasons: dict[str, list[dict[str, Any]]],
    strategy_switch_proposal: dict[str, Any] | None,
    strategy_switch_approved: dict[str, Any] | None,
    enabled_strategies_by_symbol: dict[str, dict[str, list[str]]],
    warning_codes: list[str],
) -> dict[str, Any]:
    projection = {
        "schema_version": 1,
        "runtime_id": runtime_id,
        "execution_state": _execution_state(
            plan_cfg=plan_cfg,
            execution=execution,
            event_stats=event_stats,
            lifecycle_events=lifecycle_events,
        ),
        "portfolio": portfolio,
        "positions": {
            env: _project_positions(
                plan_cfg=plan_cfg,
                portfolio_summary=portfolio.get(env),
                portfolio_obj=latest_portfolios.get(env),
            )
            for env in ("live", "sandbox")
        },
        "pending_orders": {
            env: _project_pending_orders(
                lifecycle_events.get(env, []),
                order_events=order_events.get(env, []),
            )
            for env in ("live", "sandbox")
        },
        "quotes": {
            env: _project_quotes(
                plan_cfg=plan_cfg,
                lifecycle_events=lifecycle_events.get(env, []),
                order_events=order_events.get(env, []),
                fill_events=fill_events.get(env, []),
            )
            for env in ("live", "sandbox")
        },
        "lifecycle_summary": lifecycle_stats,
        "risk_summary": {
            env: {
                **(risk_stats.get(env, {}) or {}),
                "top_risk_reject_reasons": top_lifecycle_reject_reasons.get(env, []),
            }
            for env in ("live", "sandbox")
        },
        "alerts": _project_alerts(
            warning_codes=warning_codes,
            top_lifecycle_reject_reasons=top_lifecycle_reject_reasons,
        ),
        "active_symbols": {
            env: _project_active_symbols(
                plan_cfg=plan_cfg,
                rank_events=rank_events.get(env, []),
                strategy_switch_proposal=strategy_switch_proposal if env == "live" else None,
            )
            for env in ("live", "sandbox")
        },
        "strategy_switch": {
            "proposal": strategy_switch_proposal,
            "approved": strategy_switch_approved,
            "enabled_strategies_by_symbol": enabled_strategies_by_symbol.get("live", {}),
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
    live_stats = event_stats.get("live", {})
    return {
        "runtime_mode": runtime.get("mode"),
        "broker_type": execution.get("broker_type"),
        "execution_mode": execution.get("execution_mode"),
        "confirm_live": execution.get("confirm_live") is True,
        "confirm_live_token_present": execution.get("confirm_live_token_present") is True,
        "pending_orders_count": _pending_count(lifecycle_events.get("live", [])),
        "fill_events_count": int(live_stats.get("fill_events_lines", 0) or 0),
        "source": "manifest_plan",
    }


def _project_positions(
    *,
    plan_cfg: dict[str, Any],
    portfolio_summary: dict[str, Any] | None,
    portfolio_obj: Any | None,
) -> dict[str, Any]:
    items = _positions_from_portfolio_snapshot(portfolio_obj)
    if items:
        return {"items": items, "source": "portfolio_snapshot", "empty_reason": None}

    items = _positions_from_broker_sync(portfolio_obj)
    if items:
        return {"items": items, "source": "broker_account_sync", "empty_reason": None}

    items = _positions_from_notional(plan_cfg=plan_cfg, portfolio_summary=portfolio_summary)
    if items:
        return {"items": items, "source": "notional_inferred", "empty_reason": None}

    return {"items": [], "source": "portfolio_snapshot", "empty_reason": "no_filled_position"}


def _positions_from_portfolio_snapshot(portfolio_obj: Any | None) -> list[dict[str, Any]]:
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
            }
        )
    return sorted(out, key=lambda x: (str(x.get("symbol")), str(x.get("trade_instrument_id"))))


def _positions_from_broker_sync(portfolio_obj: Any | None) -> list[dict[str, Any]]:
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
                "source": "broker_account_sync",
            }
        )
    return sorted(out, key=lambda x: str(x.get("symbol")))


def _positions_from_notional(
    *,
    plan_cfg: dict[str, Any],
    portfolio_summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(portfolio_summary, dict):
        return []
    notional = portfolio_summary.get("notional_by_symbol")
    margin = portfolio_summary.get("margin_by_symbol")
    notional_map = notional if isinstance(notional, Mapping) else {}
    margin_map = margin if isinstance(margin, Mapping) else {}
    symbols = sorted({*(str(k) for k in notional_map), *(str(k) for k in margin_map)})
    contracts = _contracts(plan_cfg)
    out: list[dict[str, Any]] = []
    for symbol in symbols:
        notional_value = _number(notional_map.get(symbol))
        margin_value = _number(margin_map.get(symbol))
        if (notional_value is None or notional_value == 0) and (
            margin_value is None or margin_value == 0
        ):
            continue
        out.append(
            {
                "symbol": symbol,
                "trade_instrument_id": contracts.get(symbol),
                "position_side": "unknown",
                "quantity": None,
                "avg_price": None,
                "unrealized_pnl": None,
                "realized_pnl": None,
                "notional": notional_value,
                "margin": margin_value,
                "updated_ts": None,
                "source": "notional_inferred",
            }
        )
    return out


def _project_pending_orders(
    lifecycle_events: list[dict[str, Any]],
    *,
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
        item = {
            "order_id": order_id,
            "symbol": _str_or_none(event.get("symbol"))
            or _str_or_none(event.get("instrument_id"))
            or _str_or_none(base_order.get("symbol"))
            or _str_or_none(base_order.get("instrument_id")),
            "trade_instrument_id": _str_or_none(event.get("trade_instrument_id"))
            or _str_or_none(base_order.get("trade_instrument_id")),
            "side": _str_or_none(event.get("side")) or _str_or_none(base_order.get("side")),
            "position_side": _str_or_none(event.get("position_side"))
            or _str_or_none(base_order.get("position_side")),
            "quantity": quantity,
            "filled_quantity": filled,
            "remaining_quantity": remaining,
            "status": status,
            "reason": _str_or_none(event.get("reason")),
            "ts": event.get("ts"),
        }
        items.append(item)
    items.sort(key=lambda x: (int(x["ts"]) if isinstance(x.get("ts"), int) else 0, x["order_id"]))
    return {"items": items, "count": len(items)}


def _project_quotes(
    *,
    plan_cfg: dict[str, Any],
    lifecycle_events: list[dict[str, Any]],
    order_events: list[dict[str, Any]],
    fill_events: list[dict[str, Any]],
) -> dict[str, Any]:
    contracts = _contracts(plan_cfg)
    symbols = set(_universe_symbols(plan_cfg)) | set(contracts)
    for event in [*order_events, *lifecycle_events, *fill_events]:
        sym = _str_or_none(event.get("symbol")) or _str_or_none(event.get("instrument_id"))
        if sym:
            symbols.add(sym)

    event_rows = [*order_events, *lifecycle_events, *fill_events]
    latest_market_by_key: dict[str, tuple[int, float, str]] = {}
    latest_exec_by_key: dict[str, tuple[int, float, str]] = {}
    latest_order_price_by_key: dict[str, tuple[int, float]] = {}
    contract_by_symbol = dict(contracts)

    for event in event_rows:
        symbol = _str_or_none(event.get("symbol")) or _str_or_none(event.get("instrument_id"))
        contract = _str_or_none(event.get("trade_instrument_id"))
        if symbol and contract:
            contract_by_symbol.setdefault(symbol, contract)
        keys = [x for x in (symbol, contract) if x]
        ts = _event_ts(event)
        market_price = _number(event.get("market_price"))
        if market_price is not None:
            for key in keys:
                _set_latest(latest_market_by_key, key, ts, market_price, "market_price")
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

    items: list[dict[str, Any]] = []
    for symbol in sorted(symbols):
        contract = contract_by_symbol.get(symbol) or contracts.get(symbol)
        market = latest_market_by_key.get(symbol) or (
            latest_market_by_key.get(contract) if contract else None
        )
        execution = latest_exec_by_key.get(symbol) or (
            latest_exec_by_key.get(contract) if contract else None
        )
        order_price = latest_order_price_by_key.get(symbol) or (
            latest_order_price_by_key.get(contract) if contract else None
        )
        available = market is not None
        reason = "ok" if available else "quote_not_recorded"
        if not contract:
            reason = "contract_quote_unmapped"
        items.append(
            {
                "symbol": symbol,
                "trade_instrument_id": contract,
                "latest_market_price": market[1] if market else None,
                "last_execution_price": execution[1] if execution else None,
                "order_price": order_price[1] if order_price else None,
                "available": available,
                "price_source": market[2] if market else "none",
                "execution_price_source": execution[2] if execution else "none",
                "reason": reason,
            }
        )
    by_symbol = {str(item["symbol"]): item for item in items if item.get("symbol")}
    by_contract = {
        str(item["trade_instrument_id"]): item
        for item in items
        if item.get("trade_instrument_id")
    }
    return {"items": items, "by_symbol": by_symbol, "by_contract": by_contract}


def _project_alerts(
    *,
    warning_codes: list[str],
    top_lifecycle_reject_reasons: dict[str, list[dict[str, Any]]],
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

    for env, reasons in top_lifecycle_reject_reasons.items():
        for reason in reasons:
            code = _str_or_none(reason.get("reason")) or "unknown_reject_reason"
            count = int(reason.get("count", 0) or 0)
            level = "error" if code.startswith("risk_") or code == "halted_by_guard" else "warning"
            items.append(
                {
                    "code": code,
                    "level": level,
                    "message": f"{code} occurred {count} time(s)",
                    "source": f"{env}.order_lifecycle_events",
                    "count": count,
                }
            )
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


def _project_active_symbols(
    *,
    plan_cfg: dict[str, Any],
    rank_events: list[dict[str, Any]],
    strategy_switch_proposal: dict[str, Any] | None,
) -> dict[str, Any]:
    latest_rank = rank_events[-1] if rank_events else None
    if isinstance(latest_rank, dict):
        active = latest_rank.get("active_symbols")
        if isinstance(active, list):
            symbols = sorted(x for x in active if isinstance(x, str))
            if symbols:
                return {
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
            "symbols": universe,
            "source": "universe",
            "explanation": "TopN disabled; using universe symbols",
        }
    return {
        "symbols": [],
        "source": "none",
        "explanation": "TopN enabled but rank_events and strategy_switch proposal are empty",
    }


def _pending_count(lifecycle_events: list[dict[str, Any]]) -> int:
    return _project_pending_orders(lifecycle_events, order_events=[])["count"]


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
    return [x for x in symbols if isinstance(x, str)]


def _contracts(plan_cfg: dict[str, Any]) -> dict[str, str]:
    instruments = plan_cfg.get("instruments")
    if not isinstance(instruments, dict):
        return {}
    roll = instruments.get("roll_policy")
    if not isinstance(roll, dict):
        return {}
    raw = roll.get("contracts")
    if not isinstance(raw, dict):
        return {}
    return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, str)}


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
