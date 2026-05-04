from __future__ import annotations

NEW = "new"
ORDER_SUBMITTED = "order_submitted"
SIMULATED_PARTIAL_FILL = "simulated_partial_fill"
SIMULATED_FILL = "simulated_fill"
TQKQ_SIM_FILL = "tqkq_sim_fill"
EXPIRED = "expired"
RISK_POSITION_LIMIT = "risk_position_limit"
RISK_MAX_RISK_RATIO = "risk_max_risk_ratio"
RISK_MAX_NOTIONAL = "risk_max_notional"
RISK_MAX_MARGIN_USED = "risk_max_margin_used"
BLOCKED_BY_PENDING_ORDER = "blocked_by_pending_order"
DUPLICATE_SAME_TICK = "duplicate_same_tick"
REJECT_NEXT_ORDER = "reject_next_order"
REJECTED_SYMBOL = "rejected_symbol"
QUANTITY_REJECTED = "quantity_rejected"
QUANTITY_BELOW_MIN_QTY = "quantity_below_min_qty"
MISSING_TRADE_INSTRUMENT_ID = "missing_trade_instrument_id"
INVALID_TRADE_INSTRUMENT_ID_MAIN_ALIAS = "invalid_trade_instrument_id_main_alias"
INVALID_TRADE_INSTRUMENT_ID_NOT_REAL_CONTRACT = "invalid_trade_instrument_id_not_real_contract"

ALLOWED_LIFECYCLE_REASONS = frozenset(
    {
        NEW,
        ORDER_SUBMITTED,
        SIMULATED_PARTIAL_FILL,
        SIMULATED_FILL,
        TQKQ_SIM_FILL,
        EXPIRED,
        RISK_POSITION_LIMIT,
        RISK_MAX_RISK_RATIO,
        RISK_MAX_NOTIONAL,
        RISK_MAX_MARGIN_USED,
        BLOCKED_BY_PENDING_ORDER,
        DUPLICATE_SAME_TICK,
        REJECT_NEXT_ORDER,
        REJECTED_SYMBOL,
        QUANTITY_REJECTED,
        QUANTITY_BELOW_MIN_QTY,
        MISSING_TRADE_INSTRUMENT_ID,
        INVALID_TRADE_INSTRUMENT_ID_MAIN_ALIAS,
        INVALID_TRADE_INSTRUMENT_ID_NOT_REAL_CONTRACT,
    }
)


def validate_lifecycle_reason(reason: str | None) -> str | None:
    if reason is None:
        return None
    if reason not in ALLOWED_LIFECYCLE_REASONS:
        raise ValueError(f"unknown lifecycle reason: {reason}")
    return reason
