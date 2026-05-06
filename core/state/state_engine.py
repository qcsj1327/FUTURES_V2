from __future__ import annotations

from core.state.application import FillApplication
from core.state.capital_model import CapitalModel
from core.state.position_lifecycle import PositionLifecycle
from domain.enums import ExecutionStatus, OrderStatus
from domain.event import FillEvent, OrderEvent
from domain.state import OrderState, PortfolioState, PositionKey, PositionState


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
        self.orders: dict[str, OrderState] = {}

    def apply_order_event(self, event: OrderEvent) -> OrderState:
        state = OrderState(
            order_id=event.order_id,
            instrument_id=event.instrument_id,
            trade_instrument_id=event.trade_instrument_id,
            side=event.side,
            position_side=event.position_side,
            quantity=event.quantity,
            status=event.status,
            ts=event.ts,
            filled_quantity=float(event.metadata.get("filled_quantity") or 0.0),
            avg_fill_price=_float_or_none(event.metadata.get("avg_fill_price")),
            client_order_id=event.client_order_id,
            runtime_id=event.runtime_id,
            strategy_name=event.strategy_name,
            reason=event.reason,
            metadata=dict(event.metadata),
        )
        self.orders[event.order_id] = state
        return state

    def apply_fill_event(self, event: FillEvent) -> tuple[OrderState, PositionState]:
        existing_order = self.orders.get(event.order_id)
        order_quantity = existing_order.quantity if existing_order is not None else event.quantity
        application = FillApplication(
            order_id=event.order_id,
            instrument_id=event.instrument_id,
            trade_instrument_id=event.trade_instrument_id,
            side=event.side,
            position_side=event.position_side,
            order_quantity=order_quantity,
            filled_quantity=event.quantity,
            fill_price=event.fill_price,
            status=_execution_status_from_fill_event(event),
            ts=event.ts,
            client_order_id=event.client_order_id,
            reason=str(event.metadata.get("reason") or "fill"),
            remaining_quantity=_float_or_none(event.metadata.get("remaining_quantity")),
            avg_fill_price=_float_or_none(event.metadata.get("avg_fill_price")) or event.fill_price,
        )
        position = self._apply_fill_to_portfolio(
            application=application,
            strategy_name=event.strategy_name,
        )
        filled_quantity = event.quantity
        if existing_order is not None:
            filled_quantity += existing_order.filled_quantity
        status = (
            OrderStatus.FILLED
            if application.status == ExecutionStatus.FILLED
            else OrderStatus.PARTIALLY_FILLED
        )
        order_state = OrderState(
            order_id=event.order_id,
            instrument_id=event.instrument_id,
            trade_instrument_id=event.trade_instrument_id,
            side=event.side,
            position_side=event.position_side,
            quantity=order_quantity,
            status=status,
            ts=event.ts,
            filled_quantity=filled_quantity,
            avg_fill_price=application.avg_fill_price,
            client_order_id=event.client_order_id,
            runtime_id=event.runtime_id,
            strategy_name=event.strategy_name,
            reason=application.reason,
            metadata=dict(event.metadata),
        )
        self.orders[event.order_id] = order_state
        return order_state, position

    def _apply_fill_to_portfolio(
        self,
        *,
        application: FillApplication,
        strategy_name: str,
    ) -> PositionState:
        key = PositionKey(
            instrument_id=application.instrument_id,
            trade_instrument_id=application.trade_instrument_id,
            position_side=application.position_side,
        )

        existing = self.portfolio.positions.get(key)

        self.capital_model.pre_validate(
            portfolio=self.portfolio,
            application=application,
        )

        position = self.position_lifecycle.apply(
            application=application,
            existing=existing,
            runtime_id=self.runtime_id,
            strategy_name=strategy_name,
        )

        positions = dict(self.portfolio.positions)
        positions[key] = position
        realized_pnl = sum(pos.realized_pnl for pos in positions.values())

        cash, equity = self.capital_model.apply(
            portfolio=self.portfolio,
            application=application,
            position=position,
        )

        self.portfolio = PortfolioState(
            runtime_id=self.runtime_id,
            positions=positions,
            cash=cash,
            equity=equity,
            realized_pnl=realized_pnl,
            unrealized_pnl=self.portfolio.unrealized_pnl,
            updated_ts=application.ts,
            metadata=self.portfolio.metadata,
        )
        self.position = position

        return position


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    if not isinstance(value, str | int | float):
        return None
    return float(value)


def _execution_status_from_fill_event(event: FillEvent) -> ExecutionStatus:
    raw = event.metadata.get("execution_status")
    if raw == ExecutionStatus.PARTIALLY_FILLED.value:
        return ExecutionStatus.PARTIALLY_FILLED
    if raw == ExecutionStatus.FILLED.value:
        return ExecutionStatus.FILLED
    remaining = _float_or_none(event.metadata.get("remaining_quantity"))
    if remaining is not None and remaining > 0:
        return ExecutionStatus.PARTIALLY_FILLED
    return ExecutionStatus.FILLED
