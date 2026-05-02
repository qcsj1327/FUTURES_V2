from __future__ import annotations

from domain.enums import Decision, PositionSide, Side
from web.viewmodels.zh_mapping import (
    zh_decision,
    zh_position_side,
    zh_reason,
    zh_router_mode,
    zh_side,
)


def test_zh_mapping_covers_core_enums() -> None:
    for d in Decision:
        assert zh_decision(d.value) != "未知决策"

    for s in Side:
        assert zh_side(s.value) != "未知方向"

    for ps in PositionSide:
        assert zh_position_side(ps.value) != "未知持仓方向"

    for m in ("priority", "weighted_vote", "netting"):
        assert zh_router_mode(m) != "未知路由"


def test_zh_mapping_covers_common_reasons() -> None:
    # Keep this list small but meaningful; extend as codes stabilize.
    for code in (
        "risk_not_allowed",
        "hold_not_executable",
        "missing_quantity",
        "invalid_quantity",
        "hold_with_directional_side",
        "triggered_hold",
        "simulated_fill",
    ):
        assert zh_reason(code) != "未知原因"
