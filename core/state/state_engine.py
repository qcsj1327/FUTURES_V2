from __future__ import annotations

from core.state.capital_model import CapitalModel
from core.state.position_lifecycle import PositionLifecycle
from domain.enums import OrderStatus
from domain.event import OrderEvent
from domain.execution import ExecutionOrder, ExecutionResult
from domain.state import PortfolioState, PositionKey, PositionState


class StateEngine:
    def __init__(
        self,
        runtime_id: str = "default",
        commission_rate: float = 0.0,
    ) -> None:
        self.runtime_id = runtime_id
        self.position = PositionState(
            instrument_id="",
            trade_instrument_id="",
        )
        self.portfolio = PortfolioState(runtime_id=runtime_id)
        self.position_lifecycle = PositionLifecycle()
        self.capital_model = CapitalModel(commission_rate=commission_rate)

    def apply(
        self,
        order: ExecutionOrder | None,
        result: ExecutionResult,
        strategy_name: str = "default",
    ) -> tuple[OrderEvent | None, PositionState]:
        if order is None:
            return None, self.position

        if order.trade_instrument_id is None:
            raise ValueError("ExecutionOrder.trade_instrument_id is required")

        if result.ts is None:
            raise ValueError("ExecutionResult.ts is required")

        event = OrderEvent(
            strategy_name=strategy_name,
            instrument_id=order.instrument_id,
            trade_instrument_id=order.trade_instrument_id,
            order_id=self._resolve_order_id(result),
            side=order.side,
            position_side=order.position_side,
            quantity=order.quantity,
            status=OrderStatus.SUBMITTED if result.success else OrderStatus.REJECTED,
            ts=result.ts,
            reason=result.reason,
        )

        if not result.success:
            return event, self.position

        key = PositionKey(
            instrument_id=order.instrument_id,
            trade_instrument_id=order.trade_instrument_id,
            position_side=order.position_side,
        )

        existing = self.portfolio.positions.get(key)

        self.capital_model.pre_validate(
            portfolio=self.portfolio,
            order=order,
            result=result,
        )

        position = self.position_lifecycle.apply(
            order=order,
            result=result,
            existing=existing,
            runtime_id=self.runtime_id,
            strategy_name=strategy_name,
        )

        positions = dict(self.portfolio.positions)
        positions[key] = position

        cash, equity = self.capital_model.apply(
            portfolio=self.portfolio,
            order=order,
            result=result,
            position=position,
        )

        self.portfolio = PortfolioState(
            runtime_id=self.runtime_id,
            positions=positions,
            cash=cash,
            equity=equity,
            realized_pnl=self.portfolio.realized_pnl,
            unrealized_pnl=self.portfolio.unrealized_pnl,
            updated_ts=result.ts,
            metadata=self.portfolio.metadata,
        )
        self.position = position

        return event, position

    def _resolve_order_id(self, result: ExecutionResult) -> str:
        if result.order_id is None:
            raise ValueError("ExecutionResult.order_id is required")
        return result.order_id
