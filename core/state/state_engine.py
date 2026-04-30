from __future__ import annotations

from domain.enums import OrderStatus, PositionSide, Side
from domain.event import OrderEvent
from domain.execution import ExecutionOrder, ExecutionResult
from domain.state import PortfolioState, PositionKey, PositionState


class StateEngine:
    def __init__(self, runtime_id: str = "default") -> None:
        self.runtime_id = runtime_id
        self.position = PositionState(
            instrument_id="",
            trade_instrument_id="",
        )
        self.portfolio = PortfolioState(runtime_id=runtime_id)

    def apply(
        self,
        order: ExecutionOrder | None,
        result: ExecutionResult,
        strategy_name: str = "default",
    ) -> tuple[OrderEvent | None, PositionState]:
        if order is None:
            return None, self.position

        if order.quantity <= 0:
            raise ValueError("invalid_position_quantity")

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

        if result.fill_price is None:
            raise ValueError("ExecutionResult.fill_price is required for successful execution")

        key = PositionKey(
            instrument_id=order.instrument_id,
            trade_instrument_id=order.trade_instrument_id,
            position_side=order.position_side,
        )

        existing = self.portfolio.positions.get(key)

        if self._is_open_order(order):
            position = self._apply_open(
                order=order,
                result=result,
                existing=existing,
                strategy_name=strategy_name,
            )
        elif self._is_close_order(order):
            position = self._apply_close(
                order=order,
                result=result,
                existing=existing,
                strategy_name=strategy_name,
            )
        else:
            raise ValueError("invalid_position_lifecycle_side")

        positions = dict(self.portfolio.positions)
        positions[key] = position

        self.portfolio = PortfolioState(
            runtime_id=self.runtime_id,
            positions=positions,
            cash=self.portfolio.cash,
            equity=self.portfolio.equity,
            realized_pnl=self.portfolio.realized_pnl,
            unrealized_pnl=self.portfolio.unrealized_pnl,
            updated_ts=result.ts,
            metadata=self.portfolio.metadata,
        )
        self.position = position

        return event, position

    def _apply_open(
        self,
        *,
        order: ExecutionOrder,
        result: ExecutionResult,
        existing: PositionState | None,
        strategy_name: str,
    ) -> PositionState:
        if result.fill_price is None:
            raise ValueError("ExecutionResult.fill_price is required for successful execution")

        if existing is None:
            return PositionState(
                instrument_id=order.instrument_id,
                trade_instrument_id=self._resolve_trade_instrument_id(order),
                position_side=order.position_side,
                quantity=order.quantity,
                avg_price=result.fill_price,
                realized_pnl=0.0,
                runtime_id=self.runtime_id,
                strategy_name=strategy_name,
                updated_ts=result.ts,
            )

        if existing.avg_price is None:
            raise ValueError("existing_position_avg_price_missing")

        total_quantity = existing.quantity + order.quantity
        avg_price = (
            (existing.quantity * existing.avg_price)
            + (order.quantity * result.fill_price)
        ) / total_quantity

        return PositionState(
            instrument_id=existing.instrument_id,
            trade_instrument_id=existing.trade_instrument_id,
            position_side=existing.position_side,
            quantity=total_quantity,
            avg_price=avg_price,
            realized_pnl=existing.realized_pnl,
            unrealized_pnl=existing.unrealized_pnl,
            runtime_id=self.runtime_id,
            strategy_name=strategy_name,
            updated_ts=result.ts,
            metadata=existing.metadata,
        )

    def _apply_close(
        self,
        *,
        order: ExecutionOrder,
        result: ExecutionResult,
        existing: PositionState | None,
        strategy_name: str,
    ) -> PositionState:
        if result.fill_price is None:
            raise ValueError("ExecutionResult.fill_price is required for successful execution")

        if existing is None or existing.quantity <= 0:
            raise ValueError("cannot_close_missing_position")

        if order.quantity > existing.quantity:
            raise ValueError("close_quantity_exceeds_position")

        if existing.avg_price is None:
            raise ValueError("existing_position_avg_price_missing")

        realized_delta = self._calculate_realized_pnl(
            position_side=order.position_side,
            avg_price=existing.avg_price,
            exit_price=result.fill_price,
            quantity=order.quantity,
        )

        return PositionState(
            instrument_id=existing.instrument_id,
            trade_instrument_id=existing.trade_instrument_id,
            position_side=existing.position_side,
            quantity=existing.quantity - order.quantity,
            avg_price=existing.avg_price,
            realized_pnl=existing.realized_pnl + realized_delta,
            unrealized_pnl=existing.unrealized_pnl,
            runtime_id=self.runtime_id,
            strategy_name=strategy_name,
            updated_ts=result.ts,
            metadata=existing.metadata,
        )

    def _is_open_order(self, order: ExecutionOrder) -> bool:
        if order.position_side == PositionSide.LONG:
            return order.side == Side.BUY
        if order.position_side == PositionSide.SHORT:
            return order.side == Side.SELL
        return False

    def _is_close_order(self, order: ExecutionOrder) -> bool:
        if order.position_side == PositionSide.LONG:
            return order.side == Side.SELL
        if order.position_side == PositionSide.SHORT:
            return order.side == Side.BUY
        return False

    def _calculate_realized_pnl(
        self,
        *,
        position_side: PositionSide,
        avg_price: float,
        exit_price: float,
        quantity: float,
    ) -> float:
        if position_side == PositionSide.LONG:
            return (exit_price - avg_price) * quantity
        if position_side == PositionSide.SHORT:
            return (avg_price - exit_price) * quantity
        raise ValueError("invalid_position_side")

    def _resolve_order_id(self, result: ExecutionResult) -> str:
        if result.order_id is None:
            raise ValueError("ExecutionResult.order_id is required")
        return result.order_id

    def _resolve_trade_instrument_id(self, order: ExecutionOrder) -> str:
        if order.trade_instrument_id is None:
            raise ValueError("ExecutionOrder.trade_instrument_id is required")
        return order.trade_instrument_id
