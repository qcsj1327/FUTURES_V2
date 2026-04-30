from __future__ import annotations

from domain.enums import PositionSide, Side
from domain.execution import ExecutionOrder, ExecutionResult
from domain.state import PositionState


class PositionLifecycle:
    def apply(
        self,
        *,
        order: ExecutionOrder,
        result: ExecutionResult,
        existing: PositionState | None,
        runtime_id: str,
        strategy_name: str,
    ) -> PositionState:
        if order.quantity <= 0:
            raise ValueError("invalid_position_quantity")

        if result.fill_price is None:
            raise ValueError("ExecutionResult.fill_price is required for successful execution")

        if self._is_open_order(order):
            return self._apply_open(
                order=order,
                result=result,
                existing=existing,
                runtime_id=runtime_id,
                strategy_name=strategy_name,
            )

        if self._is_close_order(order):
            return self._apply_close(
                order=order,
                result=result,
                existing=existing,
                runtime_id=runtime_id,
                strategy_name=strategy_name,
            )

        raise ValueError("invalid_position_lifecycle_side")

    def _apply_open(
        self,
        *,
        order: ExecutionOrder,
        result: ExecutionResult,
        existing: PositionState | None,
        runtime_id: str,
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
                runtime_id=runtime_id,
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
            runtime_id=runtime_id,
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
        runtime_id: str,
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
            runtime_id=runtime_id,
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

    def _resolve_trade_instrument_id(self, order: ExecutionOrder) -> str:
        if order.trade_instrument_id is None:
            raise ValueError("ExecutionOrder.trade_instrument_id is required")
        return order.trade_instrument_id
