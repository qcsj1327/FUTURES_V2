from __future__ import annotations

from copy import deepcopy

from core.state.state_engine import StateEngine
from domain.state import PortfolioState, PositionState


def clone_position_state(position: PositionState) -> PositionState:
    return PositionState(
        instrument_id=position.instrument_id,
        trade_instrument_id=position.trade_instrument_id,
        position_side=position.position_side,
        quantity=position.quantity,
        avg_price=position.avg_price,
        realized_pnl=position.realized_pnl,
        unrealized_pnl=position.unrealized_pnl,
        runtime_id=position.runtime_id,
        strategy_name=position.strategy_name,
        updated_ts=position.updated_ts,
        metadata=deepcopy(position.metadata),
    )


def clone_portfolio_state(portfolio: PortfolioState) -> PortfolioState:
    return PortfolioState(
        runtime_id=portfolio.runtime_id,
        positions={
            key: clone_position_state(position)
            for key, position in portfolio.positions.items()
        },
        cash=portfolio.cash,
        equity=portfolio.equity,
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=portfolio.unrealized_pnl,
        updated_ts=portfolio.updated_ts,
        metadata=deepcopy(portfolio.metadata),
    )


def clone_state_engine(state: StateEngine) -> StateEngine:
    cloned = StateEngine(
        runtime_id=state.runtime_id,
        commission_rate=state.capital_model.commission_rate,
    )
    cloned.position = clone_position_state(state.position)
    cloned.portfolio = clone_portfolio_state(state.portfolio)
    return cloned
