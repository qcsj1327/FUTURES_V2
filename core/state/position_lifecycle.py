from __future__ import annotations

from core.state.application import FillApplication
from domain.enums import ExecutionStatus, PositionSide, Side
from domain.state import PositionState


class PositionLifecycle:
    def apply(
        self,
        *,
        application: FillApplication,
        existing: PositionState | None,
        runtime_id: str,
        strategy_name: str,
    ) -> PositionState:
        filled_quantity = self._filled_quantity(application)
        fill_price = self._fill_price(application)

        if self._is_open_order(application):
            return self._apply_open(
                application=application,
                existing=existing,
                runtime_id=runtime_id,
                strategy_name=strategy_name,
                filled_quantity=filled_quantity,
                fill_price=fill_price,
            )

        if self._is_close_order(application):
            return self._apply_close(
                application=application,
                existing=existing,
                runtime_id=runtime_id,
                strategy_name=strategy_name,
                filled_quantity=filled_quantity,
                fill_price=fill_price,
            )

        raise ValueError("invalid_position_lifecycle_side")

    def _apply_open(
        self,
        *,
        application: FillApplication,
        existing: PositionState | None,
        runtime_id: str,
        strategy_name: str,
        filled_quantity: float,
        fill_price: float,
    ) -> PositionState:
        if existing is None:
            return PositionState(
                instrument_id=application.instrument_id,
                trade_instrument_id=application.trade_instrument_id,
                position_side=application.position_side,
                quantity=filled_quantity,
                avg_price=fill_price,
                realized_pnl=0.0,
                runtime_id=runtime_id,
                strategy_name=strategy_name,
                updated_ts=application.ts,
            )

        if existing.avg_price is None:
            raise ValueError("existing_position_avg_price_missing")

        total_quantity = existing.quantity + filled_quantity
        avg_price = (
            (existing.quantity * existing.avg_price)
            + (filled_quantity * fill_price)
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
            updated_ts=application.ts,
            metadata=existing.metadata,
        )

    def _apply_close(
        self,
        *,
        application: FillApplication,
        existing: PositionState | None,
        runtime_id: str,
        strategy_name: str,
        filled_quantity: float,
        fill_price: float,
    ) -> PositionState:
        if existing is None or existing.quantity <= 0:
            raise ValueError("cannot_close_missing_position")

        if filled_quantity > existing.quantity:
            raise ValueError("close_quantity_exceeds_position")

        if existing.avg_price is None:
            raise ValueError("existing_position_avg_price_missing")

        realized_delta = self._calculate_realized_pnl(
            position_side=application.position_side,
            avg_price=existing.avg_price,
            exit_price=fill_price,
            quantity=filled_quantity,
        )

        return PositionState(
            instrument_id=existing.instrument_id,
            trade_instrument_id=existing.trade_instrument_id,
            position_side=existing.position_side,
            quantity=existing.quantity - filled_quantity,
            avg_price=existing.avg_price,
            realized_pnl=existing.realized_pnl + realized_delta,
            unrealized_pnl=existing.unrealized_pnl,
            runtime_id=runtime_id,
            strategy_name=strategy_name,
            updated_ts=application.ts,
            metadata=existing.metadata,
        )

    def _filled_quantity(self, application: FillApplication) -> float:
        if application.status in {
            ExecutionStatus.FILLED,
            ExecutionStatus.PARTIALLY_FILLED,
        }:
            if application.filled_quantity is None:
                raise ValueError("ExecutionResult.filled_quantity is required")

            if application.filled_quantity <= 0:
                raise ValueError("invalid_filled_quantity")

            if application.filled_quantity > application.order_quantity:
                raise ValueError("filled_quantity_exceeds_order_quantity")

            return application.filled_quantity

        if application.order_quantity <= 0:
            raise ValueError("invalid_position_quantity")

        return application.order_quantity

    def _fill_price(self, application: FillApplication) -> float:
        fill_price = application.avg_fill_price

        if fill_price is not None:
            return fill_price

        if application.fill_price is None:
            raise ValueError("ExecutionResult.fill_price is required for successful execution")

        return application.fill_price

    def _is_open_order(self, application: FillApplication) -> bool:
        if application.position_side == PositionSide.LONG:
            return application.side == Side.BUY
        if application.position_side == PositionSide.SHORT:
            return application.side == Side.SELL
        return False

    def _is_close_order(self, application: FillApplication) -> bool:
        if application.position_side == PositionSide.LONG:
            return application.side == Side.SELL
        if application.position_side == PositionSide.SHORT:
            return application.side == Side.BUY
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
