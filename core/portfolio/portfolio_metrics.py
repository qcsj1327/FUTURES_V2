from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from core.instruments.specs import InstrumentSpecRegistry
from domain.enums import PositionSide
from domain.state import PortfolioState


@dataclass(frozen=True)
class PortfolioMetrics:
    cash: float
    equity: float
    margin_used: float
    risk_ratio: float
    unrealized_pnl: float
    realized_pnl: float
    notional_by_symbol: dict[str, float] = field(default_factory=dict)
    cost_total_sum: float = 0.0

    def as_metadata(self) -> dict[str, object]:
        return {
            "cash": self.cash,
            "equity": self.equity,
            "margin_used": self.margin_used,
            "risk_ratio": self.risk_ratio,
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
            "notional_by_symbol": dict(self.notional_by_symbol),
            "cost_total_sum": self.cost_total_sum,
        }


def calculate_portfolio_metrics(
    *,
    portfolio: PortfolioState,
    prices: Mapping[str, float],
    instrument_specs: InstrumentSpecRegistry,
    initial_equity: float,
    cost_total_sum: float,
) -> PortfolioMetrics:
    margin_used = 0.0
    unrealized_pnl = 0.0
    notional_by_symbol: dict[str, float] = {}

    for position in portfolio.positions.values():
        if position.quantity <= 0:
            continue
        price = prices.get(position.instrument_id)
        if price is None:
            price = prices.get(position.trade_instrument_id)
        if price is None:
            continue
        avg_price = position.avg_price if position.avg_price is not None else price
        spec = instrument_specs.get(position.instrument_id)
        notional = abs(price * position.quantity * spec.multiplier)
        margin = notional * spec.margin_rate if spec.margin_rate is not None else 0.0
        margin_used += margin
        notional_by_symbol[position.instrument_id] = (
            notional_by_symbol.get(position.instrument_id, 0.0) + notional
        )
        if position.position_side == PositionSide.LONG:
            unrealized_pnl += (price - avg_price) * position.quantity * spec.multiplier
        elif position.position_side == PositionSide.SHORT:
            unrealized_pnl += (avg_price - price) * position.quantity * spec.multiplier

    realized_pnl = float(portfolio.realized_pnl)
    equity = initial_equity + realized_pnl + unrealized_pnl - cost_total_sum
    cash = equity - margin_used
    risk_ratio = margin_used / equity if equity > 0 else 0.0
    return PortfolioMetrics(
        cash=cash,
        equity=equity,
        margin_used=margin_used,
        risk_ratio=risk_ratio,
        unrealized_pnl=unrealized_pnl,
        realized_pnl=realized_pnl,
        notional_by_symbol=notional_by_symbol,
        cost_total_sum=cost_total_sum,
    )
