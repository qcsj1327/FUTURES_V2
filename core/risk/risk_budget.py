from __future__ import annotations

from core.portfolio.portfolio_engine import PortfolioAllocation
from domain.state import PortfolioState


class RiskBudget:
    def __init__(self, risk_budget: float | None = None) -> None:
        self.risk_budget = risk_budget

    def adjust_quantity(
        self,
        *,
        allocation: PortfolioAllocation,
        portfolio: PortfolioState | None,
        price: float | None,
        stop_loss_distance: float | None,
    ) -> float | None:
        if self.risk_budget is None:
            return allocation.quantity

        if allocation.quantity is None:
            return None

        # 没有止损信息，不做调整
        if stop_loss_distance is None or stop_loss_distance <= 0:
            return allocation.quantity

        # 计算最大允许数量
        max_qty = self.risk_budget / stop_loss_distance

        # 不允许放大仓位
        qty = min(allocation.quantity, max_qty)

        # 资金约束（如果有 cash）
        if portfolio is not None and portfolio.cash is not None and price is not None:
            max_affordable = portfolio.cash / price
            qty = min(qty, max_affordable)

        return qty
