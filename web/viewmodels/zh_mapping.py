from __future__ import annotations

from domain.enums import Decision, PositionSide, Side

# Router modes
ROUTER_MODE_ZH: dict[str, str] = {
    "priority": "优先级路由",
    "weighted_vote": "权重投票",
    "netting": "净额合并",
}

# Decisions
DECISION_ZH: dict[str, str] = {
    Decision.OPEN_LONG.value: "开多",
    Decision.OPEN_SHORT.value: "开空",
    Decision.CLOSE.value: "平仓",
    Decision.HOLD.value: "观望",
}

SIDE_ZH: dict[str, str] = {
    Side.BUY.value: "买入",
    Side.SELL.value: "卖出",
    Side.NONE.value: "无",
}

POSITION_SIDE_ZH: dict[str, str] = {
    PositionSide.LONG.value: "多",
    PositionSide.SHORT.value: "空",
    PositionSide.FLAT.value: "空仓",
}

MODE_ZH: dict[str, str] = {
    "simulated_v2": "模拟行情",
    "simulated": "模拟行情",
    "live_file": "本地行情",
    "tqkq_sim": "天勤模拟",
    "tqkq_live": "天勤实盘",
    "dry_run": "仅演练",
    "live": "真实下单",
}

STATUS_ZH: dict[str, str] = {
    "NEW": "新建",
    "SUBMITTED": "已提交",
    "PARTIAL": "部分成交",
    "FILLED": "已成交",
    "CANCELED": "已撤单",
    "EXPIRED": "已过期",
    "REJECTED": "已拒绝",
}

# Common execution / chain reasons (extend as new codes appear)
REASON_ZH: dict[str, str] = {
    # execution engine
    "risk_not_allowed": "风控不允许",
    "hold_not_executable": "观望不可执行",
    "missing_quantity": "缺少下单数量",
    "invalid_quantity": "下单数量非法",
    "hold_with_directional_side": "观望但方向字段不一致",
    "triggered_hold": "触发后观望",
    # broker/sim
    "new": "新建",
    "order_submitted": "已提交",
    "simulated_fill": "模拟成交",
    "simulated_partial_fill": "模拟部分成交",
    "tqkq_sim_fill": "天勤模拟成交",
    "tqkq_live_partial_fill": "天勤实盘部分成交",
    "tqkq_live_fill": "天勤实盘成交",
    "blocked_by_pending_order": "待处理订单阻塞",
    "duplicate_same_tick": "同 tick 重复下单",
    "expired": "订单过期",
    "canceled": "已撤单",
    "risk_position_limit": "超过持仓数量上限",
    "risk_max_notional": "超过名义金额上限",
    "risk_max_risk_ratio": "超过风险度上限",
    "risk_max_margin_used": "超过保证金占用上限",
    "rate_limited": "触发限频",
    "halted_by_guard": "触发熔断",
    "roll_cancel_pending": "换月撤单中",
    "roll_close_position": "换月清仓中",
    "roll_cooldown_block": "换月观察期阻断",
    "missing_trade_instrument_id": "缺少执行合约",
    "invalid_trade_instrument_id_main_alias": "执行合约不能为主力别名",
    "invalid_trade_instrument_id_not_real_contract": "执行合约不是真实合约",
    "quote_not_recorded": "未记录行情价",
    "contract_quote_unmapped": "合约未映射行情",
    "missing_candidate_summary": "缺少候选摘要",
    "missing_decision": "缺少决策结果",
    "missing_approved": "缺少审批结果",
    "missing_strategy_switch_approved": "缺少策略切换审批",
    # promotion gate (typical)
    "insufficient_events": "样本不足",
    "insufficient_success_rate_improvement": "胜率提升不足",
    "max_consecutive_failures_exceeded": "连续失败超阈值",
}


def zh_router_mode(mode: str | None) -> str:
    if mode is None:
        return "未知路由"
    return ROUTER_MODE_ZH.get(mode, "未知路由")


def zh_decision(decision_code: str | None) -> str:
    if decision_code is None:
        return "未知决策"
    return DECISION_ZH.get(decision_code, "未知决策")


def zh_reason(reason_code: str | None) -> str:
    if reason_code is None:
        return "未知原因"
    return REASON_ZH.get(reason_code, "未知原因")


def zh_mode(mode_code: str | None) -> str:
    if mode_code is None:
        return "未知模式"
    return MODE_ZH.get(mode_code, mode_code)


def zh_status(status_code: str | None) -> str:
    if status_code is None:
        return "未知状态"
    return STATUS_ZH.get(status_code, status_code)


def zh_side(side_code: str | None) -> str:
    if side_code is None:
        return "未知方向"
    return SIDE_ZH.get(side_code, "未知方向")


def zh_position_side(code: str | None) -> str:
    if code is None:
        return "未知持仓方向"
    return POSITION_SIDE_ZH.get(code, "未知持仓方向")
