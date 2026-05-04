from __future__ import annotations

from core.execution.lifecycle_reasons import (
    RISK_MAX_MARGIN_USED,
    RISK_MAX_NOTIONAL,
    RISK_MAX_RISK_RATIO,
)
from core.instruments.specs import InstrumentSpecRegistry
from core.portfolio.portfolio_metrics import PortfolioMetrics
from domain.execution import ExecutionOrder


class PortfolioRiskLimits:
    def __init__(
        self,
        *,
        max_risk_ratio: float | None = None,
        max_margin_used: float | None = None,
        max_notional_by_symbol: dict[str, float] | None = None,
    ) -> None:
        self.max_risk_ratio = max_risk_ratio
        self.max_margin_used = max_margin_used
        self.max_notional_by_symbol = dict(max_notional_by_symbol or {})

    def reject_reason(
        self,
        *,
        order: ExecutionOrder,
        market_price: float,
        metrics: PortfolioMetrics,
        instrument_specs: InstrumentSpecRegistry,
    ) -> str | None:
        spec = instrument_specs.get(order.instrument_id)
        order_notional = abs(market_price * order.quantity * spec.multiplier)
        current_notional = metrics.notional_by_symbol.get(order.instrument_id, 0.0)
        notional_limit = self.max_notional_by_symbol.get(order.instrument_id)
        if notional_limit is not None and current_notional + order_notional > notional_limit:
            return RISK_MAX_NOTIONAL

        if self.max_risk_ratio is not None:
            order_margin = (
                order_notional * spec.margin_rate if spec.margin_rate is not None else 0.0
            )
            if self.max_margin_used is not None and (
                metrics.margin_used + order_margin > self.max_margin_used
            ):
                return RISK_MAX_MARGIN_USED
            projected = (
                (metrics.margin_used + order_margin) / metrics.equity
                if metrics.equity > 0
                else float("inf")
            )
            if projected > self.max_risk_ratio:
                return RISK_MAX_RISK_RATIO
        elif self.max_margin_used is not None:
            order_margin = (
                order_notional * spec.margin_rate if spec.margin_rate is not None else 0.0
            )
            if metrics.margin_used + order_margin > self.max_margin_used:
                return RISK_MAX_MARGIN_USED

        return None
