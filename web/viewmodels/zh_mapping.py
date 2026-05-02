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
    "simulated_fill": "模拟成交",
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


def zh_side(side_code: str | None) -> str:
    if side_code is None:
        return "未知方向"
    return SIDE_ZH.get(side_code, "未知方向")


def zh_position_side(code: str | None) -> str:
    if code is None:
        return "未知持仓方向"
    return POSITION_SIDE_ZH.get(code, "未知持仓方向")
